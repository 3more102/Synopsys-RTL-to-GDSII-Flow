#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "mmmc_coverage_policy.json"
DEFAULT_EXPORTER = ROOT / "scripts" / "common" / "export_mmmc_config.tcl"
DEFAULT_JSON = ROOT / "reports" / "mmmc" / "mmmc_coverage.json"
DEFAULT_MD = ROOT / "reports" / "mmmc" / "mmmc_coverage.md"


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str
    subject: str = ""


def truthy(value: Any) -> bool:
    return str(value).strip().lower() not in {"", "0", "false", "no", "off"}


def parse_export(text: str) -> dict[str, dict[str, dict[str, Any]]]:
    data: dict[str, dict[str, dict[str, Any]]] = {"corners": {}, "modes": {}, "scenarios": {}}
    for raw in text.splitlines():
        if not raw.strip():
            continue
        parts = raw.rstrip("\n").split("\t")
        kind = parts[0]
        if kind == "CORNER" and len(parts) >= 5:
            data["corners"][parts[1]] = {"purpose": parts[2], "rc": parts[3], "lib": parts[4]}
        elif kind == "MODE" and len(parts) >= 4:
            data["modes"][parts[1]] = {"enabled": truthy(parts[2]), "sdc": parts[3]}
        elif kind == "SCENARIO" and len(parts) >= 5:
            data["scenarios"][parts[1]] = {"enabled": truthy(parts[2]), "mode": parts[3], "corner": parts[4]}
    return data


def load_config(root: Path, exporter: Path) -> dict[str, dict[str, dict[str, Any]]]:
    proc = subprocess.run(["tclsh", str(exporter)], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(f"MMMC Tcl export failed rc={proc.returncode}: {proc.stderr.strip()}")
    return parse_export(proc.stdout)


def resolve_file(root: Path, raw: str) -> Path:
    p = Path(os.path.expandvars(os.path.expanduser(raw)))
    return p if p.is_absolute() else (root / p)


def audit(root: Path, data: dict[str, Any], policy: dict[str, Any], require_enabled: bool = False, require_evidence: bool = False) -> dict[str, Any]:
    corners = data.get("corners", {})
    modes = data.get("modes", {})
    scenarios = data.get("scenarios", {})
    findings: list[Finding] = []
    enabled_modes = {n:d for n,d in modes.items() if truthy(d.get("enabled"))}
    enabled_scenarios = {n:d for n,d in scenarios.items() if truthy(d.get("enabled"))}

    for sc_name, sc in scenarios.items():
        mode = sc.get("mode", ""); corner = sc.get("corner", "")
        if mode not in modes:
            findings.append(Finding("ERROR", "UNKNOWN_MODE", f"Scenario references unknown mode '{mode}'.", sc_name))
        if corner not in corners:
            findings.append(Finding("ERROR", "UNKNOWN_CORNER", f"Scenario references unknown corner '{corner}'.", sc_name))

    for mode_name, mode in enabled_modes.items():
        sdc = str(mode.get("sdc", "")).strip()
        if policy.get("require_mode_sdc_for_enabled_mode", True):
            if not sdc:
                findings.append(Finding("ERROR", "ENABLED_MODE_NO_SDC", "Enabled mode has no SDC configured.", mode_name))
            elif not resolve_file(root, sdc).is_file():
                findings.append(Finding("ERROR", "ENABLED_MODE_SDC_MISSING", f"Configured SDC does not exist: {sdc}", mode_name))

    coverage: dict[str, set[str]] = {name:set() for name in enabled_modes}
    evidence: list[dict[str, Any]] = []
    expected_rc = policy.get("expected_rc_by_purpose", {})
    templates = policy.get("scenario_report_templates", {})

    for sc_name, sc in enabled_scenarios.items():
        mode_name = sc.get("mode", ""); corner_name = sc.get("corner", "")
        mode = modes.get(mode_name); corner = corners.get(corner_name)
        if mode is None or corner is None:
            continue
        if policy.get("require_enabled_mode_for_enabled_scenario", True) and not truthy(mode.get("enabled")):
            findings.append(Finding("ERROR", "SCENARIO_USES_DISABLED_MODE", f"Enabled scenario uses disabled mode '{mode_name}'.", sc_name))
        lib = str(corner.get("lib", "")).strip()
        if policy.get("require_corner_library_for_enabled_scenario", True):
            if not lib:
                findings.append(Finding("ERROR", "ENABLED_SCENARIO_NO_LIBRARY", f"Corner '{corner_name}' has no real PVT library configured.", sc_name))
            elif not resolve_file(root, lib).exists():
                findings.append(Finding("ERROR", "CORNER_LIBRARY_MISSING", f"Configured corner library does not exist: {lib}", sc_name))
        purpose = str(corner.get("purpose", "")).strip().lower()
        if mode_name in coverage and purpose:
            coverage[mode_name].add(purpose)
        expected = str(expected_rc.get(purpose, "")).strip().lower()
        actual_rc = str(corner.get("rc", "")).strip().lower()
        if expected and actual_rc and actual_rc != expected:
            findings.append(Finding("ERROR", "RC_ROLE_MISMATCH", f"Corner purpose '{purpose}' expects RC role '{expected}' but corner uses '{actual_rc}'.", corner_name))
        if require_evidence and purpose in templates:
            rel = templates[purpose].format(scenario=sc_name, mode=mode_name, corner=corner_name)
            p = root / rel
            present = p.is_file() and p.stat().st_size > 0
            evidence.append({"scenario": sc_name, "purpose": purpose, "path": rel, "present": present})
            if not present:
                findings.append(Finding("ERROR", "SCENARIO_EVIDENCE_MISSING", f"Expected scenario report is missing or empty: {rel}", sc_name))

    required_purposes = [str(x).lower() for x in policy.get("required_purposes_per_enabled_mode", ["setup", "hold"])]
    for mode_name in enabled_modes:
        missing = [p for p in required_purposes if p not in coverage.get(mode_name, set())]
        if missing and enabled_scenarios:
            findings.append(Finding("ERROR", "MODE_COVERAGE_INCOMPLETE", f"Enabled mode lacks scenario coverage for: {', '.join(missing)}", mode_name))

    if require_enabled and not enabled_scenarios:
        findings.append(Finding("ERROR", "NO_ENABLED_SCENARIOS", "No MMMC scenarios are enabled but enabled scenario coverage is required."))

    counts = {sev: sum(1 for f in findings if f.severity == sev) for sev in ("ERROR", "WARNING", "INFO")}
    if counts["ERROR"]:
        status = "FAIL"
    elif not enabled_scenarios:
        status = "UNKNOWN"
    else:
        status = "PASS"

    matrix = []
    for sc_name, sc in scenarios.items():
        corner = corners.get(sc.get("corner", ""), {})
        matrix.append({
            "scenario": sc_name,
            "enabled": truthy(sc.get("enabled")),
            "mode": sc.get("mode", ""),
            "corner": sc.get("corner", ""),
            "purpose": corner.get("purpose", ""),
            "rc": corner.get("rc", ""),
            "library_configured": bool(str(corner.get("lib", "")).strip()),
        })
    return {
        "schema_version": 1,
        "status": status,
        "enabled_modes": sorted(enabled_modes),
        "enabled_scenarios": sorted(enabled_scenarios),
        "coverage": {k: sorted(v) for k,v in coverage.items()},
        "matrix": matrix,
        "evidence": evidence,
        "counts": counts,
        "findings": [asdict(f) for f in findings],
        "limitations": "Structural/evidence audit only. It does not parse timing slack from scenario reports or replace signoff STA review."
    }


def write_reports(result: dict[str, Any], json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True); md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    lines = ["# MMMC Coverage Audit", "", f"**Status:** {result['status']}", f"**Enabled modes:** {', '.join(result['enabled_modes']) or 'none'}", f"**Enabled scenarios:** {', '.join(result['enabled_scenarios']) or 'none'}", "", "| Scenario | Enabled | Mode | Corner | Purpose | RC | Library configured |", "|---|---|---|---|---|---|---|"]
    for row in result["matrix"]:
        lines.append(f"| {row['scenario']} | {row['enabled']} | {row['mode']} | {row['corner']} | {row['purpose']} | {row['rc']} | {row['library_configured']} |")
    lines += ["", "## Findings", ""]
    if result["findings"]:
        for f in result["findings"]:
            lines.append(f"- **{f['severity']} {f['code']}** `{f['subject']}` — {f['message']}")
    else:
        lines.append("No structural findings.")
    if result["evidence"]:
        lines += ["", "## Scenario evidence", "", "| Scenario | Purpose | Report | Present |", "|---|---|---|---|"]
        for e in result["evidence"]:
            lines.append(f"| {e['scenario']} | {e['purpose']} | `{e['path']}` | {e['present']} |")
    md_path.write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate MMMC structural and scenario signoff coverage.")
    ap.add_argument("--root", default=str(ROOT)); ap.add_argument("--policy", default=str(DEFAULT_POLICY)); ap.add_argument("--exporter", default=str(DEFAULT_EXPORTER)); ap.add_argument("--json", default=str(DEFAULT_JSON)); ap.add_argument("--markdown", default=str(DEFAULT_MD)); ap.add_argument("--require-enabled", action="store_true"); ap.add_argument("--require-evidence", action="store_true")
    args = ap.parse_args(); root=Path(args.root).resolve(); policy=json.loads(Path(args.policy).read_text())
    if policy.get("schema_version") != 1: raise SystemExit("unsupported MMMC coverage policy schema")
    data=load_config(root, Path(args.exporter)); result=audit(root, data, policy, args.require_enabled, args.require_evidence); write_reports(result, Path(args.json), Path(args.markdown))
    print(f"MMMC_AUDIT status={result['status']} enabled_scenarios={len(result['enabled_scenarios'])} errors={result['counts']['ERROR']} report={args.markdown}")
    return 1 if result["status"] == "FAIL" else 0

if __name__ == "__main__": raise SystemExit(main())
