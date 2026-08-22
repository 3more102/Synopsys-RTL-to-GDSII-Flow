#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SIGNATURES = ROOT / "config" / "failure_signatures.json"
DEFAULT_OUT = ROOT / "reports" / "triage"


def load_signatures(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError(f"unsupported failure signature schema_version={data.get('schema_version')!r}")
    signatures = data.get("signatures")
    if not isinstance(signatures, list) or not signatures:
        raise ValueError("failure signature database must contain a non-empty signatures list")
    seen: set[str] = set()
    for item in signatures:
        if not isinstance(item, dict):
            raise ValueError("failure signature entries must be objects")
        sig_id = str(item.get("id", ""))
        if not sig_id or sig_id in seen:
            raise ValueError(f"invalid or duplicate failure signature id: {sig_id!r}")
        seen.add(sig_id)
        patterns = item.get("patterns")
        if not isinstance(patterns, list) or not patterns:
            raise ValueError(f"failure signature {sig_id!r} has no patterns")
        for pattern in patterns:
            re.compile(str(pattern), re.IGNORECASE)
    return signatures


def normalize_line(line: str, max_chars: int = 600) -> str:
    text = line.rstrip("\r\n")
    if len(text) > max_chars:
        text = text[: max_chars - 3] + "..."
    return text


def classify(text: str, signatures: list[dict[str, Any]], max_evidence: int = 4) -> list[dict[str, Any]]:
    lines = text.splitlines()
    findings: list[dict[str, Any]] = []
    for signature in signatures:
        compiled = [re.compile(str(p), re.IGNORECASE) for p in signature["patterns"]]
        evidence: list[dict[str, Any]] = []
        matched_patterns: set[str] = set()
        total_hits = 0
        for lineno, line in enumerate(lines, 1):
            for raw_pattern, pattern in zip(signature["patterns"], compiled):
                if pattern.search(line):
                    total_hits += 1
                    matched_patterns.add(str(raw_pattern))
                    if len(evidence) < max_evidence:
                        evidence.append({"line": lineno, "text": normalize_line(line), "pattern": str(raw_pattern)})
                    break
        if total_hits:
            findings.append(
                {
                    "id": signature["id"],
                    "category": signature.get("category", "unclassified"),
                    "priority": int(signature.get("priority", 0)),
                    "hit_count": total_hits,
                    "matched_patterns": sorted(matched_patterns),
                    "evidence": evidence,
                    "guidance": list(signature.get("guidance", [])),
                }
            )
    findings.sort(key=lambda f: (-f["priority"], -f["hit_count"], f["id"]))
    return findings


def build_result(log: Path, stage: str, tool: str, exit_code: int | None, signatures: list[dict[str, Any]]) -> dict[str, Any]:
    text = log.read_text(encoding="utf-8", errors="replace")
    findings = classify(text, signatures)
    primary = findings[0] if findings else None
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "tool": tool,
        "exit_code": exit_code,
        "log": str(log.resolve()),
        "classification_status": "CLASSIFIED" if findings else "UNCLASSIFIED",
        "confidence": "heuristic",
        "root_cause_proven": False,
        "primary_category": primary["category"] if primary else "unclassified",
        "primary_signature": primary["id"] if primary else None,
        "findings": findings,
        "note": "Failure signatures are investigation hints derived from log text. They do not prove root cause or replace tool reports/manual diagnosis.",
    }


def write_markdown(result: dict[str, Any], path: Path) -> None:
    lines = [
        f"# Failure Triage — {result['stage']}",
        "",
        f"- Tool: `{result['tool'] or 'UNKNOWN'}`",
        f"- Exit code: `{result['exit_code'] if result['exit_code'] is not None else 'UNKNOWN'}`",
        f"- Classification: **{result['classification_status']}**",
        f"- Primary category: `{result['primary_category']}`",
        f"- Root cause proven: **NO**",
        f"- Source log: `{result['log']}`",
        "",
        "> These matches are conservative investigation hints. They do not prove root cause or signoff status.",
    ]
    if not result["findings"]:
        lines.extend(
            [
                "",
                "## No known signature matched",
                "",
                "Inspect the earliest error/warning cluster in the source log and the stage-specific reports. Do not infer a design or tool root cause from the exit code alone.",
            ]
        )
    for finding in result["findings"]:
        lines.extend(
            [
                "",
                f"## {finding['id']}",
                "",
                f"Category: `{finding['category']}`  ",
                f"Priority: `{finding['priority']}`  ",
                f"Matched lines: `{finding['hit_count']}`",
                "",
                "### Evidence",
                "",
            ]
        )
        for item in finding["evidence"]:
            lines.append(f"- Line {item['line']}: `{item['text'].replace('`', chr(39))}`")
        lines.extend(["", "### Suggested investigation", ""])
        for guidance in finding["guidance"]:
            lines.append(f"- {guidance}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Heuristically classify failed ASIC EDA stage logs without claiming root cause.")
    ap.add_argument("--log", required=True)
    ap.add_argument("--stage", default="unknown")
    ap.add_argument("--tool", default="")
    ap.add_argument("--exit-code", type=int)
    ap.add_argument("--signatures", default=str(DEFAULT_SIGNATURES))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--json-out")
    ap.add_argument("--md-out")
    args = ap.parse_args()

    log = Path(args.log).resolve()
    if not log.is_file():
        print(f"ERROR: triage log not found: {log}", file=sys.stderr)
        return 2
    try:
        signatures = load_signatures(Path(args.signatures).resolve())
        result = build_result(log, args.stage, args.tool, args.exit_code, signatures)
    except (OSError, ValueError, json.JSONDecodeError, re.error) as exc:
        print(f"ERROR: failure triage could not initialize: {exc}", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", args.stage).strip("_") or "unknown"
    json_out = Path(args.json_out).resolve() if args.json_out else out_dir / f"{slug}.latest.json"
    md_out = Path(args.md_out).resolve() if args.md_out else out_dir / f"{slug}.latest.md"
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(result, md_out)

    print(f"TRIAGE_STATUS={result['classification_status']}")
    print(f"TRIAGE_PRIMARY={result['primary_signature'] or 'NONE'}")
    print(f"TRIAGE_CATEGORY={result['primary_category']}")
    print(f"TRIAGE_JSON={json_out}")
    print(f"TRIAGE_MARKDOWN={md_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
