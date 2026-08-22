#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CURRENT = ROOT / "reports" / "provenance" / "run_provenance.json"
DEFAULT_POLICY = ROOT / "config" / "provenance_policy.json"
DEFAULT_JSON = ROOT / "reports" / "provenance" / "provenance_comparison.json"
DEFAULT_MD = ROOT / "reports" / "provenance" / "provenance_comparison.md"


def map_files(group: dict[str, Any]) -> dict[str, str]:
    return {x.get("path", ""): x.get("sha256", "") for x in group.get("files", [])}


def detail_group(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    of = map_files(old); nf = map_files(new)
    files = {
        "added": sorted(set(nf) - set(of)),
        "removed": sorted(set(of) - set(nf)),
        "changed": sorted(p for p in set(of) & set(nf) if of[p] != nf[p]),
    }
    oe = old.get("environment", {}); ne = new.get("environment", {})
    env_changed = sorted(k for k in set(oe) | set(ne) if oe.get(k) != ne.get(k))
    ox = old.get("external_paths", {}); nx = new.get("external_paths", {})
    external_changed = sorted(k for k in set(ox) | set(nx) if ox.get(k) != nx.get(k))
    tools_changed = []
    ot = old.get("tools", {}); nt = new.get("tools", {})
    tools_changed = sorted(k for k in set(ot) | set(nt) if ot.get(k) != nt.get(k))
    return {"files": files, "environment_changed": env_changed, "external_paths_changed": external_changed, "tools_changed": tools_changed}


def compare(baseline: dict[str, Any], current: dict[str, Any], policy: dict[str, Any], strict_execution: bool = False) -> dict[str, Any]:
    if baseline.get("schema_version") != 1 or current.get("schema_version") != 1:
        return {"schema_version": 1, "status": "FAIL", "errors": ["unsupported provenance schema"], "groups": {}}
    severity_cfg = policy.get("comparison_severity", {})
    groups = {}; fail = False; warn = False
    all_names = sorted(set(baseline.get("groups", {})) | set(current.get("groups", {})))
    for name in all_names:
        old = baseline.get("groups", {}).get(name, {}); new = current.get("groups", {}).get(name, {})
        same = old.get("digest") == new.get("digest") and bool(old.get("digest"))
        severity = severity_cfg.get(name, "WARNING")
        if strict_execution and name == "execution": severity = "FAIL"
        state = "MATCH" if same else "DIFF"
        if not same and severity == "FAIL": fail = True
        elif not same: warn = True
        groups[name] = {"state": state, "severity": severity, "baseline_digest": old.get("digest", ""), "current_digest": new.get("digest", ""), "details": {} if same else detail_group(old, new)}
    status = "FAIL" if fail else "WARNING" if warn else "PASS"
    return {"schema_version": 1, "status": status, "baseline_provenance_digest": baseline.get("provenance_digest", ""), "current_provenance_digest": current.get("provenance_digest", ""), "groups": groups, "errors": []}


def write_reports(result: dict[str, Any], json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True); md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    lines = ["# Provenance Comparison", "", f"**Status:** {result['status']}", "", "| Group | State | Severity |", "|---|---|---|"]
    for name, info in result.get("groups", {}).items():
        lines.append(f"| {name} | {info['state']} | {info['severity']} |")
    lines += [""]
    for name, info in result.get("groups", {}).items():
        if info["state"] == "MATCH": continue
        d = info.get("details", {}); lines += [f"## {name}", f"- Added files: {', '.join(d.get('files',{}).get('added',[])) or 'none'}", f"- Removed files: {', '.join(d.get('files',{}).get('removed',[])) or 'none'}", f"- Changed files: {', '.join(d.get('files',{}).get('changed',[])) or 'none'}", f"- Environment changed: {', '.join(d.get('environment_changed',[])) or 'none'}", f"- External paths changed: {', '.join(d.get('external_paths_changed',[])) or 'none'}", f"- Tools changed: {', '.join(d.get('tools_changed',[])) or 'none'}", ""]
    md_path.write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare ASIC run provenance against a baseline.")
    ap.add_argument("--baseline", required=True); ap.add_argument("--current", default=str(DEFAULT_CURRENT)); ap.add_argument("--policy", default=str(DEFAULT_POLICY)); ap.add_argument("--json", default=str(DEFAULT_JSON)); ap.add_argument("--markdown", default=str(DEFAULT_MD)); ap.add_argument("--strict-execution", action="store_true")
    args = ap.parse_args()
    baseline_path = Path(args.baseline); current_path = Path(args.current)
    if not baseline_path.is_file(): raise SystemExit(f"baseline provenance not found: {baseline_path}")
    if not current_path.is_file(): raise SystemExit(f"current provenance not found: {current_path}")
    policy = json.loads(Path(args.policy).read_text()); strict = args.strict_execution or os.environ.get("STRICT_EXECUTION", "0") == "1"
    result = compare(json.loads(baseline_path.read_text()), json.loads(current_path.read_text()), policy, strict)
    write_reports(result, Path(args.json), Path(args.markdown)); print(f"PROVENANCE_COMPARE status={result['status']} report={args.markdown}")
    return 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__": raise SystemExit(main())
