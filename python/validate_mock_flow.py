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
from rich_qor import metric_value, parse_area, parse_cts, parse_power_detail, parse_route, parse_timing  # noqa: E402

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
        errors.append(f"missing file: {path}"); return
    first_lines = read(path).splitlines()[:2]
    if not any(MOCK_HEADER in line for line in first_lines):
        errors.append(f"missing mock safety header: {path}")


def validate_mock_run(run: Path) -> dict[str, Any]:
    run = run.resolve(); errors: list[str] = []; warnings: list[str] = []
    marker = run / "MOCK_RUN.json"
    if not marker.is_file():
        return {"status": "FAIL", "errors": [f"missing MOCK_RUN.json: {marker}"], "warnings": [], "metrics": {}}
    try: meta = json.loads(marker.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "FAIL", "errors": [f"invalid MOCK_RUN.json: {exc}"], "warnings": [], "metrics": {}}
    if meta.get("mock") is not True: errors.append("MOCK_RUN.json must contain mock=true")
    if meta.get("signoff_qualified") is not False: errors.append("mock run must explicitly set signoff_qualified=false")
    scenario = meta.get("scenario", ""); project = meta.get("project", "MOCK_CHIP")

    required_reports = [
        run / "reports/synthesis/qor.rpt", run / "reports/synthesis/area.rpt", run / "reports/synthesis/power.rpt",
        run / "reports/placement/utilization.rpt", run / "reports/placement/congestion.rpt",
        run / "reports/cts/post_cts_clock_timing.rpt", run / "reports/cts/qor.rpt", run / "reports/cts/hold.rpt",
        run / "reports/signoff/setup.rpt", run / "reports/signoff/hold.rpt", run / "reports/signoff/summary.rpt", run / "reports/signoff/clock_timing.rpt",
        run / "reports/route/route_status.rpt", run / "reports/route/congestion.rpt", run / "reports/power/vectorless_power.rpt", run / "logs/10_synthesis_mock.log",
    ]
    for path in required_reports: require_mock_header(path, errors)

    synthesis_qor = read(run / "reports/synthesis/qor.rpt"); signoff_qor = read(run / "reports/signoff/summary.rpt")
    setup_text = read(run / "reports/signoff/setup.rpt"); hold_text = read(run / "reports/signoff/hold.rpt")
    area_text = read(run / "reports/synthesis/area.rpt"); power_text = read(run / "reports/power/vectorless_power.rpt")
    congestion_text = read(run / "reports/placement/congestion.rpt"); route_text = read(run / "reports/route/route_status.rpt")
    cts_text = read(run / "reports/cts/post_cts_clock_timing.rpt")

    synth_wns, synth_tns, synth_viol = parse_qor(synthesis_qor)
    rich_timing = parse_timing(signoff_qor, "setup")
    if scenario == "multi_corner":
        scenario_rows = rich_timing.get("scenarios", [])
        wns_values = [metric_value(row, "setup_wns_ns") for row in scenario_rows]
        tns_values = [metric_value(row, "setup_tns_ns") for row in scenario_rows]
        viol_values = [metric_value(row, "setup_violations") for row in scenario_rows]
        if len(scenario_rows) != 2 or any(v is None for v in wns_values):
            errors.append("multi_corner scenario must preserve exactly two parsed timing scenarios")
            signoff_wns = signoff_tns = setup_viol = None
        else:
            signoff_wns = min(float(v) for v in wns_values if v is not None)
            signoff_tns = min(float(v) for v in tns_values if v is not None) if all(v is not None for v in tns_values) else None
            setup_viol = sum(int(v) for v in viol_values if v is not None) if all(v is not None for v in viol_values) else None
    else:
        signoff_wns, signoff_tns, setup_viol = parse_qor(signoff_qor)

    area, _, cells = parse_area_util(area_text); power = parse_power(power_text); congestion = parse_congestion(congestion_text); drc = parse_drc(route_text)
    setup_slack = slack_from_timing(setup_text); hold_slack = slack_from_timing(hold_text); hold_viol = violated_path_count(hold_text)

    rich_area = parse_area(area_text); rich_power = parse_power_detail(power_text); rich_cts = parse_cts(cts_text); rich_route = parse_route(route_text); rich_congestion = parse_route(congestion_text)
    metrics = {
        "synthesis_wns": synth_wns, "synthesis_tns": synth_tns, "synthesis_violations": synth_viol,
        "signoff_wns": signoff_wns, "signoff_tns": signoff_tns, "setup_violations": setup_viol,
        "setup_slack": setup_slack, "hold_slack": hold_slack, "hold_violations": hold_viol,
        "area": area, "cell_count": cells, "power": power, "congestion": congestion, "drc": drc,
        "comb_area": metric_value(rich_area, "combinational_area_um2"), "seq_area": metric_value(rich_area, "sequential_area_um2"), "macro_area": metric_value(rich_area, "macro_area_um2"),
        "internal_power": metric_value(rich_power, "internal_w"), "switching_power": metric_value(rich_power, "switching_w"), "leakage_power": metric_value(rich_power, "leakage_w"),
        "clock_skew": metric_value(rich_cts, "clock_skew_ns"), "clock_latency": metric_value(rich_cts, "network_latency_ns"),
        "wire_length": metric_value(rich_route, "wire_length_um"), "via_count": metric_value(rich_route, "via_count"), "route_overflow": metric_value(rich_congestion, "total_overflow"),
    }
    for key, value in metrics.items():
        if value is None: errors.append(f"existing/rich parser could not prove mock metric: {key}")

    setup_status = status_value(run / "reports/status/setup_sta.status"); hold_status = status_value(run / "reports/status/hold_sta.status")
    drc_status = status_value(run / "reports/status/drc.status"); synth_status = status_value(run / "reports/status/synthesis.status")

    if scenario == "clean":
        if signoff_wns is None or signoff_wns < 0 or signoff_tns is None or signoff_tns < 0 or setup_viol != 0: errors.append("clean mock scenario must parse as timing-clean mock evidence")
        if hold_slack is None or hold_slack < 0 or hold_viol != 0: errors.append("clean mock scenario must parse as hold-clean mock evidence")
        if drc != 0: errors.append("clean mock scenario must parse DRC=0")
        if setup_status != "MOCK_PASS" or hold_status != "MOCK_PASS" or drc_status != "MOCK_PASS": errors.append("clean mock statuses must remain MOCK_PASS, never PASS")
    elif scenario == "timing_fail":
        if signoff_wns is None or signoff_wns >= 0 or setup_viol is None or setup_viol <= 0: errors.append("timing_fail scenario did not produce a proven setup violation")
        if setup_status != "MOCK_FAIL": errors.append("timing_fail setup status must be MOCK_FAIL")
    elif scenario == "hold_fail":
        if hold_slack is None or hold_slack >= 0 or hold_viol <= 0: errors.append("hold_fail scenario did not produce a proven hold violation")
        if hold_status != "MOCK_FAIL": errors.append("hold_fail hold status must be MOCK_FAIL")
    elif scenario == "drc_fail":
        if drc is None or drc <= 0: errors.append("drc_fail scenario did not produce DRC violations")
        if drc_status != "MOCK_FAIL": errors.append("drc_fail DRC status must be MOCK_FAIL")
    elif scenario == "multi_corner":
        scenarios = {row.get("context", {}).get("scenario") for row in rich_timing.get("scenarios", [])}
        if scenarios != {"FUNC_SS_MOCK", "FUNC_FF_MOCK"}: errors.append("multi_corner scenario identities were not preserved")
        if signoff_wns is None or signoff_wns >= 0 or setup_status != "MOCK_FAIL": errors.append("multi_corner worst setup corner must be a deterministic MOCK_FAIL")
    elif scenario == "qor_regression":
        if area is None or area < 13000 or power is None or power <= 0.01: errors.append("qor_regression scenario must increase deterministic area and power")
        if setup_status != "MOCK_PASS" or drc_status != "MOCK_PASS": errors.append("qor_regression is a QoR delta scenario, not a design-failure scenario")
    elif scenario == "license_fail":
        log = read(run / "logs/10_synthesis_mock.log").lower()
        if "license checkout failed" not in log or synth_status != "MOCK_FAIL": errors.append("license_fail scenario lacks deterministic license-failure evidence")
    elif scenario == "missing_artifact":
        spef = run / f"spef/{project}_postroute.spef"
        if spef.exists(): errors.append("missing_artifact scenario unexpectedly generated SPEF")
        if status_value(run / "reports/status/extraction.status") != "MOCK_FAIL": errors.append("missing_artifact extraction status must be MOCK_FAIL")
    else:
        errors.append(f"unknown scenario in marker: {scenario}")

    for rel in [f"results/synthesis/{project}_syn.v", f"results/synthesis/{project}_syn.sdc", f"netlist/{project}_postroute.v", f"results/final/{project}_final.sdc", f"sdf/{project}_postroute.sdf", f"gds/{project}.gds"]:
        require_mock_header(run / rel, errors)
    spef = run / f"spef/{project}_postroute.spef"
    if scenario != "missing_artifact": require_mock_header(spef, errors)

    status = "PASS" if not errors else "FAIL"
    return {"schema_version": 1, "mock": True, "signoff_qualified": False, "scenario": scenario, "status": status, "errors": errors, "warnings": warnings, "metrics": metrics}


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate deterministic mock ASIC evidence using the repository's real report parsers.")
    ap.add_argument("run", help="Path to mock run directory"); ap.add_argument("--report", default="", help="Optional validation JSON output")
    args = ap.parse_args(); run = Path(args.run)
    if not run.is_absolute(): run = ROOT / run
    result = validate_mock_run(run); report_path = Path(args.report) if args.report else run / "MOCK_VALIDATION.json"
    if not report_path.is_absolute(): report_path = ROOT / report_path
    report_path.parent.mkdir(parents=True, exist_ok=True); report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"MOCK_VALIDATION_STATUS={result['status']}"); print(f"MOCK_VALIDATION={report_path}")
    for error in result["errors"]: print(f"ERROR: {error}", file=sys.stderr)
    return 0 if result["status"] == "PASS" else 3


if __name__ == "__main__": raise SystemExit(main())
