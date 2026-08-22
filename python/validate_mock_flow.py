#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from qor_parsers import parse_area_util, parse_congestion, parse_drc, parse_power, parse_qor  # noqa: E402
from report_utils import slack_from_timing, violated_path_count  # noqa: E402

MOCK_HEADER = "MOCK DATA - NOT SIGNOFF"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def status_value(path: Path) -> str:
    for line in read(path).splitlines():
        if line.startswith("status="):
            return line.split("=", 1)[1].strip()
    return "UNKNOWN"


def require_mock_header(path: Path, errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"missing file: {path}")
        return
    if MOCK_HEADER not in read(path).splitlines()[:2]:
        errors.append(f"missing mock safety header: {path}")


def validate_mock_run(run: Path) -> dict[str, Any]:
    run = run.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    marker = run / "MOCK_RUN.json"
    if not marker.is_file():
        return {"status": "FAIL", "errors": [f"missing MOCK_RUN.json: {marker}"], "warnings": [], "metrics": {}}
    try:
        meta = json.loads(marker.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "FAIL", "errors": [f"invalid MOCK_RUN.json: {exc}"], "warnings": [], "metrics": {}}
    if meta.get("mock") is not True:
        errors.append("MOCK_RUN.json must contain mock=true")
    if meta.get("signoff_qualified") is not False:
        errors.append("mock run must explicitly set signoff_qualified=false")
    scenario = meta.get("scenario", "")
    project = meta.get("project", "MOCK_CHIP")

    required_reports = [
        run / "reports/synthesis/qor.rpt",
        run / "reports/synthesis/area.rpt",
        run / "reports/synthesis/power.rpt",
        run / "reports/placement/utilization.rpt",
        run / "reports/placement/congestion.rpt",
        run / "reports/signoff/setup.rpt",
        run / "reports/signoff/hold.rpt",
        run / "reports/signoff/summary.rpt",
        run / "reports/route/route_status.rpt",
        run / "reports/power/vectorless_power.rpt",
        run / "logs/10_synthesis_mock.log",
    ]
    for path in required_reports:
        require_mock_header(path, errors)

    synthesis_qor = read(run / "reports/synthesis/qor.rpt")
    signoff_qor = read(run / "reports/signoff/summary.rpt")
    setup_text = read(run / "reports/signoff/setup.rpt")
    hold_text = read(run / "reports/signoff/hold.rpt")
    area_text = read(run / "reports/synthesis/area.rpt")
    power_text = read(run / "reports/power/vectorless_power.rpt")
    congestion_text = read(run / "reports/placement/congestion.rpt")
    drc_text = read(run / "reports/route/route_status.rpt")

    synth_wns, synth_tns, synth_viol = parse_qor(synthesis_qor)
    signoff_wns, signoff_tns, setup_viol = parse_qor(signoff_qor)
    area, _, cells = parse_area_util(area_text)
    power = parse_power(power_text)
    congestion = parse_congestion(congestion_text)
    drc = parse_drc(drc_text)
    setup_slack = slack_from_timing(setup_text)
    hold_slack = slack_from_timing(hold_text)
    hold_viol = violated_path_count(hold_text)

    metrics = {
        "synthesis_wns": synth_wns,
        "synthesis_tns": synth_tns,
        "synthesis_violations": synth_viol,
        "signoff_wns": signoff_wns,
        "signoff_tns": signoff_tns,
        "setup_violations": setup_viol,
        "setup_slack": setup_slack,
        "hold_slack": hold_slack,
        "hold_violations": hold_viol,
        "area": area,
        "cell_count": cells,
        "power": power,
        "congestion": congestion,
        "drc": drc,
    }
    for key, value in metrics.items():
        if value is None:
            errors.append(f"existing parser could not prove mock metric: {key}")

    setup_status = status_value(run / "reports/status/setup_sta.status")
    drc_status = status_value(run / "reports/status/drc.status")
    synth_status = status_value(run / "reports/status/synthesis.status")

    if scenario == "clean":
        if signoff_wns is None or signoff_wns < 0 or signoff_tns is None or signoff_tns < 0 or setup_viol != 0:
            errors.append("clean mock scenario must parse as timing-clean mock evidence")
        if hold_slack is None or hold_slack < 0 or hold_viol != 0:
            errors.append("clean mock scenario must parse as hold-clean mock evidence")
        if drc != 0:
            errors.append("clean mock scenario must parse DRC=0")
        if setup_status != "MOCK_PASS" or drc_status != "MOCK_PASS":
            errors.append("clean mock statuses must remain MOCK_PASS, never PASS")
    elif scenario == "timing_fail":
        if signoff_wns is None or signoff_wns >= 0 or setup_viol is None or setup_viol <= 0:
            errors.append("timing_fail scenario did not produce a proven setup violation")
        if setup_status != "MOCK_FAIL":
            errors.append("timing_fail setup status must be MOCK_FAIL")
    elif scenario == "drc_fail":
        if drc is None or drc <= 0:
            errors.append("drc_fail scenario did not produce DRC violations")
        if drc_status != "MOCK_FAIL":
            errors.append("drc_fail DRC status must be MOCK_FAIL")
    elif scenario == "license_fail":
        log = read(run / "logs/10_synthesis_mock.log").lower()
        if "license checkout failed" not in log or synth_status != "MOCK_FAIL":
            errors.append("license_fail scenario lacks deterministic license-failure evidence")
    elif scenario == "missing_artifact":
        spef = run / f"spef/{project}_postroute.spef"
        if spef.exists():
            errors.append("missing_artifact scenario unexpectedly generated SPEF")
        if status_value(run / "reports/status/extraction.status") != "MOCK_FAIL":
            errors.append("missing_artifact extraction status must be MOCK_FAIL")
    else:
        errors.append(f"unknown scenario in marker: {scenario}")

    # Mock artifacts must live only under the supplied mock root and remain clearly labeled.
    for rel in [
        f"results/synthesis/{project}_syn.v",
        f"results/synthesis/{project}_syn.sdc",
        f"netlist/{project}_postroute.v",
        f"results/final/{project}_final.sdc",
        f"sdf/{project}_postroute.sdf",
        f"gds/{project}.gds",
    ]:
        require_mock_header(run / rel, errors)
    spef = run / f"spef/{project}_postroute.spef"
    if scenario != "missing_artifact":
        require_mock_header(spef, errors)

    status = "PASS" if not errors else "FAIL"
    return {
        "schema_version": 1,
        "mock": True,
        "signoff_qualified": False,
        "scenario": scenario,
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "metrics": metrics,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate deterministic mock ASIC evidence using the repository's real report parsers.")
    ap.add_argument("run", help="Path to mock run directory")
    ap.add_argument("--report", default="", help="Optional validation JSON output")
    args = ap.parse_args()
    run = Path(args.run)
    if not run.is_absolute():
        run = ROOT / run
    result = validate_mock_run(run)
    report_path = Path(args.report) if args.report else run / "MOCK_VALIDATION.json"
    if not report_path.is_absolute():
        report_path = ROOT / report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"MOCK_VALIDATION_STATUS={result['status']}")
    print(f"MOCK_VALIDATION={report_path}")
    for error in result["errors"]:
        print(f"ERROR: {error}", file=sys.stderr)
    return 0 if result["status"] == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
