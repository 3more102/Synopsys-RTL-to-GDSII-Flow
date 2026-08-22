#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "config" / "artifact_provenance.json"
DEFAULT_GRAPH = ROOT / "config" / "stage_graph.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def canonical_stage(stage: str, contract: dict[str, Any], graph: dict[str, Any]) -> str:
    stage = contract.get("aliases", {}).get(stage, stage)
    return graph.get("aliases", {}).get(stage, stage)


def substitute(pattern: str, project: str) -> str:
    return pattern.replace("${PROJECT_NAME}", project)


def check_pattern(root: Path, pattern: str) -> dict[str, Any]:
    matches = sorted(root.glob(pattern), key=lambda p: p.as_posix())
    valid: list[str] = []
    invalid: list[dict[str, str]] = []
    for raw in matches:
        try:
            resolved = raw.resolve()
        except OSError as exc:
            invalid.append({"path": str(raw), "reason": f"resolve failed: {exc}"})
            continue
        rel = str(raw.relative_to(root)) if inside(root, raw) else str(raw)
        if not inside(root, resolved):
            invalid.append({"path": rel, "reason": "resolved path escapes project root"})
            continue
        if not resolved.is_file():
            invalid.append({"path": rel, "reason": "not a regular file"})
            continue
        try:
            size = resolved.stat().st_size
        except OSError as exc:
            invalid.append({"path": rel, "reason": f"stat failed: {exc}"})
            continue
        if size <= 0:
            invalid.append({"path": rel, "reason": "file is empty"})
            continue
        valid.append(str(resolved.relative_to(root)))
    return {
        "pattern": pattern,
        "matched": [str(p.relative_to(root)) if inside(root, p) else str(p) for p in matches],
        "valid": valid,
        "invalid": invalid,
        "satisfied": bool(valid),
    }


def validate_stage(
    root: Path,
    stage: str,
    contract: dict[str, Any],
    graph: dict[str, Any],
    project: str,
) -> dict[str, Any]:
    canonical = canonical_stage(stage, contract, graph)
    cfg = contract.get("stages", {}).get(canonical)
    if cfg is None:
        return {
            "schema_version": 1,
            "stage": canonical,
            "requested_stage": stage,
            "configured": False,
            "status": "SKIP",
            "required_patterns": [],
            "missing_required": [],
            "invalid_required": [],
            "detail": "stage has no artifact output contract",
        }

    checks: list[dict[str, Any]] = []
    missing: list[str] = []
    invalid: list[dict[str, str]] = []
    for raw in cfg.get("required", []):
        pattern = substitute(str(raw), project)
        result = check_pattern(root, pattern)
        checks.append(result)
        if not result["matched"]:
            missing.append(pattern)
        if result["matched"] and not result["valid"]:
            invalid.extend(result["invalid"])
        elif result["invalid"]:
            # A glob may match multiple files. One valid file satisfies the pattern,
            # but invalid siblings remain evidence worth reporting.
            invalid.extend(result["invalid"])

    failed = any(not item["satisfied"] for item in checks)
    status = "FAIL" if failed else "PASS"
    detail = (
        "all required output patterns have at least one non-empty regular file inside the project root"
        if status == "PASS"
        else "one or more required output patterns are missing or unusable"
    )
    return {
        "schema_version": 1,
        "stage": canonical,
        "requested_stage": stage,
        "configured": True,
        "status": status,
        "required_patterns": checks,
        "missing_required": missing,
        "invalid_required": invalid,
        "detail": detail,
    }


def write_report(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate required generated outputs before a successful ASIC stage is trusted.")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--stage", required=True)
    ap.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    ap.add_argument("--graph", default=str(DEFAULT_GRAPH))
    ap.add_argument("--report", default="", help="Optional JSON evidence path. Default: reports/status/<stage>_outputs.json")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    project = os.environ.get("PROJECT_NAME", "MIPS_16")
    try:
        contract = load_json(Path(args.contract).resolve())
        graph = load_json(Path(args.graph).resolve())
        result = validate_stage(root, args.stage, contract, graph, project)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    report_path = Path(args.report) if args.report else root / "reports" / "status" / f"{result['stage']}_outputs.json"
    if not report_path.is_absolute():
        report_path = root / report_path
    write_report(report_path, result)

    print(f"STAGE_OUTPUT_STATUS={result['status']}")
    print(f"STAGE_OUTPUT_STAGE={result['stage']}")
    print(f"STAGE_OUTPUT_REPORT={report_path}")
    for pattern in result.get("missing_required", []):
        print(f"MISSING_REQUIRED_OUTPUT={pattern}", file=sys.stderr)
    for item in result.get("invalid_required", []):
        print(f"INVALID_REQUIRED_OUTPUT={item['path']} reason={item['reason']}", file=sys.stderr)
    if result["status"] == "FAIL":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
