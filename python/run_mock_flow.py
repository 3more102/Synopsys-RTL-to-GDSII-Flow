#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MOCK_HEADER = "MOCK DATA - NOT SIGNOFF"
SCENARIOS = {"clean", "timing_fail", "hold_fail", "drc_fail", "license_fail", "missing_artifact", "multi_corner", "qor_regression"}


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    atomic_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def report(body: str) -> str:
    return f"{MOCK_HEADER}\n{body.rstrip()}\n"


def status_body(stage: str, status: str, detail: str) -> str:
    return report(f"stage={stage}\nstatus={status}\nmock=true\ndetail={detail}\ntime=MOCK_TIME")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_mock_artifact(path: Path, kind: str, project: str) -> None:
    if path.suffix == ".v":
        body = f"// {MOCK_HEADER}\nmodule {project.lower()}_mock; endmodule\n"
    elif path.suffix == ".sdc":
        body = f"# {MOCK_HEADER}\n# No real timing constraints are represented by this mock file.\n"
    elif path.suffix == ".spef":
        body = f"*COMMENT \"{MOCK_HEADER}\"\n*DESIGN \"{project}\"\n"
    elif path.suffix == ".sdf":
        body = f"// {MOCK_HEADER}\n(DELAYFILE (SDFVERSION \"4.0\"))\n"
    elif path.suffix == ".gds":
        body = f"{MOCK_HEADER}\nThis is a text placeholder, not GDSII stream data.\n"
    else:
        body = f"{MOCK_HEADER}\nMock artifact kind={kind} project={project}\n"
    atomic_text(path, body)


def scenario_metrics(scenario: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "synth_wns": 0.35, "synth_tns": 0.0, "synth_viol": 0,
        "signoff_wns": 0.08, "signoff_tns": 0.0, "setup_viol": 0,
        "hold_slack": 0.04, "hold_viol": 0, "drc": 0,
        "area": 12345.0, "cells": 321, "util": 0.64,
        "congestion": 0.02, "power": 0.0095,
        "clock_skew_ns": 0.041, "clock_latency_ns": 0.730,
        "wire_um": 1_425_000.0, "vias": 91_234,
    }
    if scenario == "timing_fail":
        metrics.update(signoff_wns=-0.12, signoff_tns=-1.84, setup_viol=6)
    elif scenario == "hold_fail":
        metrics.update(hold_slack=-0.025, hold_viol=4)
    elif scenario == "drc_fail":
        metrics.update(drc=3, congestion=0.11)
    elif scenario == "qor_regression":
        metrics.update(area=13332.6, power=0.0125, congestion=0.055, clock_skew_ns=0.070, wire_um=1_540_000.0)
    return metrics


def rich_power_body(total_w: float) -> str:
    internal = total_w * 0.55; switching = total_w * 0.40; leakage = total_w * 0.05
    return (
        f"Internal Power : {internal * 1000:.6f} mW\n"
        f"Switching Power : {switching * 1000:.6f} mW\n"
        f"Leakage Power : {leakage * 1000:.6f} mW\n"
        f"Total Power : {total_w * 1000:.6f} mW"
    )


def generate_mock_run(out: Path, scenario: str, project: str = "MOCK_CHIP", force: bool = False) -> dict[str, Any]:
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown mock scenario: {scenario}")
    out = out.resolve()
    if out.exists() and any(out.iterdir()):
        if not force:
            raise ValueError(f"mock output directory is not empty: {out}; use --force to replace mock-only output")
        marker = out / "MOCK_RUN.json"
        if not marker.is_file():
            raise ValueError(f"refusing --force because existing directory is not a recognized mock run: {out}")
        old = json.loads(marker.read_text(encoding="utf-8"))
        if old.get("mock") is not True:
            raise ValueError(f"refusing --force because mock marker is invalid: {marker}")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    m = scenario_metrics(scenario)
    atomic_json(out / "MOCK_RUN.json", {
        "schema_version": 1, "mock": True, "signoff_qualified": False,
        "scenario": scenario, "project": project, "top": f"{project.lower()}_mock",
        "technology": "MOCK_TECHNOLOGY_NOT_SIGNOFF", "generator": "python/run_mock_flow.py",
        "generated_at": datetime.now(timezone.utc).isoformat(), "notice": MOCK_HEADER,
    })

    atomic_text(out / "reports/synthesis/qor.rpt", report(
        f"Scenario : MOCK_SYNTH\nMode : FUNC\nCorner : MOCK_SYNTH\nWNS : {m['synth_wns']:.3f} ns\nTNS : {m['synth_tns']:.3f} ns\nNo. of Violating Paths : {m['synth_viol']}"
    ))
    comb = m["area"] * 0.57; seq = m["area"] * 0.35; macro = m["area"] - comb - seq
    atomic_text(out / "reports/synthesis/area.rpt", report(
        f"Total cell area : {m['area']:.3f} um2\nCombinational area : {comb:.3f} um2\nSequential area : {seq:.3f} um2\nMacro area : {macro:.3f} um2\n"
        f"Number of cells : {m['cells']}\nCombinational Cell Count : {int(m['cells'] * 0.60)}\nSequential Cell Count : {int(m['cells'] * 0.38)}\nMacro Count : 2\nUtilization Ratio : {m['util'] * 100:.3f} %"
    ))
    atomic_text(out / "reports/synthesis/power.rpt", report(rich_power_body(m["power"])))

    atomic_text(out / "reports/placement/utilization.rpt", report(
        f"Total Cell Area : {m['area'] * 1.01:.3f} um2\nUtilization Ratio : {m['util'] * 100:.3f} %\nCell Count : {m['cells'] + 8}"
    ))
    atomic_text(out / "reports/placement/congestion.rpt", report(
        f"Global Route Congestion : {m['congestion'] * 100:.3f} %\nHorizontal Overflow : {m['congestion'] * 60:.3f} %\n"
        f"Vertical Overflow : {m['congestion'] * 40:.3f} %\nTotal Overflow : {m['congestion'] * 100:.3f} %\nCongested Bins : {max(1, int(m['congestion'] * 1000))}"
    ))

    atomic_text(out / "reports/cts/post_cts_clock_timing.rpt", report(
        f"Clock Name : clk\nClock Skew : {m['clock_skew_ns'] * 1000:.3f} ps\nSource Latency : 0.120 ns\nNetwork Latency : {m['clock_latency_ns']:.3f} ns\n"
        f"Total Latency : {m['clock_latency_ns'] + 0.120:.3f} ns\nMax Transition : 85 ps\nSink Count : 1248\nBuffer Count : 142\nInverter Count : 23\nClock Cell Count : 165\nClock Tree Levels : 9"
    ))
    atomic_text(out / "reports/cts/qor.rpt", report(
        f"Scenario : MOCK_CTS\nWNS : {m['signoff_wns'] + 0.05:.3f} ns\nTNS : 0.000 ns\nNo. of Violating Paths : 0"
    ))
    atomic_text(out / "reports/cts/hold.rpt", report(f"slack (MET) {max(m['hold_slack'] + 0.01, 0.005):.3f} ns"))

    setup_line = f"slack ({'VIOLATED' if m['setup_viol'] else 'MET'}) {m['signoff_wns']:.3f} ns"
    setup_extra = "\n".join([setup_line] * max(1, int(m["setup_viol"])))
    hold_line = f"slack ({'VIOLATED' if m['hold_viol'] else 'MET'}) {m['hold_slack']:.3f} ns"
    hold_extra = "\n".join([hold_line] * max(1, int(m["hold_viol"])))
    atomic_text(out / "reports/signoff/setup.rpt", report(setup_extra))
    atomic_text(out / "reports/signoff/hold.rpt", report(hold_extra))
    if scenario == "multi_corner":
        summary_body = (
            "Scenario : FUNC_SS_MOCK\nMode : FUNC\nCorner : SS_MOCK\nPath Group : REG2REG\nWNS : -0.030 ns\nTNS : -0.240 ns\nNo. of Violating Paths : 3\n"
            "Scenario : FUNC_FF_MOCK\nMode : FUNC\nCorner : FF_MOCK\nPath Group : REG2REG\nWNS : 0.120 ns\nTNS : 0.000 ns\nNo. of Violating Paths : 0"
        )
    else:
        summary_body = f"Scenario : FUNC_MOCK\nMode : FUNC\nCorner : MOCK_CORNER\nPath Group : REG2REG\nWNS : {m['signoff_wns']:.3f} ns\nTNS : {m['signoff_tns']:.3f} ns\nNo. of Violating Paths : {m['setup_viol']}"
    atomic_text(out / "reports/signoff/summary.rpt", report(summary_body))
    atomic_text(out / "reports/signoff/clock_timing.rpt", report(
        f"Clock Name : clk\nClock Skew : {m['clock_skew_ns'] * 1000:.3f} ps\nNetwork Latency : {m['clock_latency_ns']:.3f} ns\nMax Transition : 85 ps\nSink Count : 1248"
    ))

    atomic_text(out / "reports/route/route_status.rpt", report(
        f"DRC violations : {m['drc']}\nTotal Wire Length : {m['wire_um'] / 1000:.3f} mm\nVia Count : {m['vias']:,}\nShort Count : {m['drc']}\nOpen Count : 0"
    ))
    atomic_text(out / "reports/route/congestion.rpt", report(
        f"Global Route Congestion : {m['congestion'] * 100:.3f} %\nTotal Overflow : {m['congestion'] * 100:.3f} %"
    ))
    atomic_text(out / "reports/power/vectorless_power.rpt", report(rich_power_body(m["power"]) + "\nActivity Source : MOCK_VECTORLESS"))

    setup_status = "MOCK_FAIL" if scenario in {"timing_fail", "multi_corner"} else "MOCK_PASS"
    hold_status = "MOCK_FAIL" if scenario == "hold_fail" else "MOCK_PASS"
    drc_status = "MOCK_FAIL" if scenario == "drc_fail" else "MOCK_PASS"
    stage_status = {
        "synthesis": "MOCK_PASS", "formal": "MOCK_PASS", "floorplan": "MOCK_PASS", "placement": "MOCK_PASS",
        "cts": "MOCK_PASS", "post_route": "MOCK_PASS", "extraction": "MOCK_PASS",
        "signoff": "MOCK_FAIL" if setup_status == "MOCK_FAIL" or hold_status == "MOCK_FAIL" else "MOCK_PASS",
        "setup_sta": setup_status, "hold_sta": hold_status, "power": "MOCK_PASS", "drc": drc_status,
        "lvs": "MOCK_PASS", "gds": "MOCK_GENERATED",
    }
    if scenario == "license_fail": stage_status["synthesis"] = "MOCK_FAIL"
    if scenario == "missing_artifact": stage_status["extraction"] = "MOCK_FAIL"
    for stage, status in stage_status.items():
        atomic_text(out / f"reports/status/{stage}.status", status_body(stage, status, f"deterministic mock scenario={scenario}; not engineering evidence"))

    for stage, duration in {"synthesis": 7, "placement": 13, "cts": 9, "route_opt": 18, "signoff": 5}.items():
        atomic_json(out / f"reports/runtime/{stage}.latest.json", {
            "schema_version": 1, "mock": True, "stage": stage, "tool": f"mock_{stage}", "flow_run_id": f"MOCK_{scenario}",
            "duration_seconds": duration, "exit_code": 1 if scenario == "license_fail" and stage == "synthesis" else 0,
        })

    if scenario == "license_fail":
        atomic_text(out / "logs/10_synthesis_mock.log", report("ERROR: License checkout failed: no valid license for mock_dc_ultra\nMock process exited with code 1"))
    else:
        atomic_text(out / "logs/10_synthesis_mock.log", report("Mock synthesis completed. No proprietary tool was launched."))

    artifacts = [
        (out / f"results/synthesis/{project}_syn.v", "synthesis_netlist"), (out / f"results/synthesis/{project}_syn.sdc", "synthesis_sdc"),
        (out / f"netlist/{project}_postroute.v", "postroute_netlist"), (out / f"results/final/{project}_final.sdc", "final_sdc"),
        (out / f"sdf/{project}_postroute.sdf", "sdf"), (out / f"gds/{project}.gds", "gds_placeholder"),
    ]
    if scenario != "missing_artifact": artifacts.append((out / f"spef/{project}_postroute.spef", "spef"))
    for path, kind in artifacts: write_mock_artifact(path, kind, project)

    hashes = {str(path.relative_to(out)): sha256(path) for path, _ in artifacts if path.is_file()}
    atomic_json(out / "MOCK_ARTIFACT_HASHES.json", {"mock": True, "sha256": hashes})
    return {"root": str(out), "scenario": scenario, "project": project, "metrics": m, "artifacts": sorted(hashes)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate deterministic, clearly-labeled mock ASIC reports/artifacts for orchestration tests.")
    ap.add_argument("--output", default="", help="Mock run directory. Default: work/mock_runs/<scenario>")
    ap.add_argument("--scenario", choices=sorted(SCENARIOS), default="clean")
    ap.add_argument("--project", default="MOCK_CHIP")
    ap.add_argument("--force", action="store_true", help="Replace an existing directory only when it contains a valid MOCK_RUN.json marker.")
    args = ap.parse_args(); output = Path(args.output) if args.output else ROOT / "work" / "mock_runs" / args.scenario
    if not output.is_absolute(): output = ROOT / output
    try: result = generate_mock_run(output, args.scenario, args.project, args.force)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr); return 2
    print(f"MOCK_RUN={result['root']}"); print(f"MOCK_SCENARIO={result['scenario']}"); print("MOCK_SIGNOFF_QUALIFIED=false"); return 0


if __name__ == "__main__": raise SystemExit(main())
