#!/usr/bin/env python3
"""Build normalized, auditable stage metrics from existing ASIC reports.

This is a sidecar model: legacy qor_summary.json remains supported while richer
consumers can use reports/metrics/*.json. No numeric metric is invented when a
report or field is missing.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from report_utils import status_record
from rich_qor import parse_area, parse_cts, parse_physical_verification, parse_power_detail, parse_route, parse_timing

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "reports" / "metrics"

STAGES: dict[str, dict[str, Any]] = {
    "synthesis": {"status": "synthesis", "runtime": "synthesis", "sources": [
        ("timing", "reports/synthesis/qor.rpt", "setup"), ("timing", "reports/synthesis/timing_min.rpt", "hold"),
        ("area", "reports/synthesis/area.rpt", ""), ("power", "reports/synthesis/power.rpt", ""),
    ]},
    "floorplan": {"status": "floorplan", "runtime": "floorplan", "sources": [
        ("timing", "reports/floorplan/qor.rpt", "setup"), ("timing", "reports/floorplan/hold.rpt", "hold"), ("area", "reports/floorplan/utilization.rpt", ""),
    ]},
    "placement": {"status": "placement", "runtime": "placement", "sources": [
        ("timing", "reports/placement/qor.rpt", "setup"), ("timing", "reports/placement/hold.rpt", "hold"), ("area", "reports/placement/utilization.rpt", ""), ("route", "reports/placement/congestion.rpt", ""),
    ]},
    "pre_cts": {"status": "pre_cts", "runtime": "pre_cts", "sources": [
        ("timing", "reports/pre_cts/qor.rpt", "setup"), ("timing", "reports/pre_cts/hold.rpt", "hold"), ("area", "reports/pre_cts/utilization.rpt", ""), ("route", "reports/pre_cts/congestion.rpt", ""),
    ]},
    "cts": {"status": "cts", "runtime": "cts", "sources": [
        ("timing", "reports/cts/qor.rpt", "setup"), ("timing", "reports/cts/hold.rpt", "hold"), ("cts", "reports/cts/post_cts_clock_timing.rpt", ""),
    ]},
    "post_cts_opt": {"status": "post_cts_opt", "runtime": "post_cts", "sources": [
        ("timing", "reports/post_cts_opt/qor.rpt", "setup"), ("timing", "reports/post_cts_opt/hold.rpt", "hold"), ("area", "reports/post_cts_opt/utilization.rpt", ""),
    ]},
    "route": {"status": "route", "runtime": "route", "sources": [
        ("timing", "reports/route/qor.rpt", "setup"), ("timing", "reports/route/hold.rpt", "hold"), ("area", "reports/route/utilization.rpt", ""), ("route", "reports/route/congestion.rpt", ""), ("route", "reports/route/route_status.rpt", ""),
    ]},
    "post_route": {"status": "post_route", "runtime": "route_opt", "sources": [
        ("timing", "reports/post_route/qor.rpt", "setup"), ("timing", "reports/post_route/hold.rpt", "hold"), ("area", "reports/post_route/utilization.rpt", ""), ("route", "reports/post_route/congestion.rpt", ""), ("route", "reports/post_route/route_status.rpt", ""),
    ]},
    "signoff": {"status": "signoff", "runtime": "signoff", "sources": [
        ("timing", "reports/signoff/summary.rpt", "setup"), ("timing", "reports/signoff/setup.rpt", "setup"), ("timing", "reports/signoff/hold.rpt", "hold"), ("cts", "reports/signoff/clock_timing.rpt", ""), ("power", "reports/power/vectorless_power.rpt", ""),
    ]},
    "drc": {"status": "drc", "runtime": "drc_prep", "sources": [("drc", "reports/physical/drc.rpt", "")]},
    "lvs": {"status": "lvs", "runtime": "lvs_prep", "sources": [("lvs", "reports/physical/lvs.rpt", "")]},
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def classification(root: Path) -> tuple[str, bool | None, str]:
    marker = load_json(root / "MOCK_RUN.json")
    if marker.get("mock") is True:
        return "MOCK", False, str(marker.get("scenario", ""))
    return "REAL", None, ""


def runtime_record(root: Path, name: str) -> dict[str, Any]:
    data = load_json(root / "reports" / "runtime" / f"{name}.latest.json")
    if not data:
        return {"available": False}
    keys = ("stage", "tool", "tool_path", "flow_run_id", "duration_seconds", "exit_code", "git_commit", "git_dirty", "input_digest")
    return {"available": True, **{k: data.get(k) for k in keys}}


def provenance_identity(root: Path) -> dict[str, Any]:
    p = load_json(root / "reports" / "provenance" / "run_provenance.json")
    git = p.get("git") if isinstance(p.get("git"), dict) else {}
    return {
        "project": p.get("project", os.environ.get("PROJECT_NAME", "MIPS_16")),
        "top": p.get("top_module", os.environ.get("TOP_MODULE", "mips_16")),
        "git_commit": git.get("commit", ""), "branch": git.get("branch", ""), "dirty": git.get("dirty", ""),
        "provenance_digest": p.get("provenance_digest", ""),
    }


def parse_source(kind: str, text: str, analysis: str) -> dict[str, Any]:
    if kind == "timing": return parse_timing(text, analysis or "setup")
    if kind == "area": return parse_area(text)
    if kind == "power": return parse_power_detail(text)
    if kind == "cts": return parse_cts(text)
    if kind == "route": return parse_route(text)
    if kind in {"drc", "lvs"}: return parse_physical_verification(text, kind)
    raise ValueError(f"unknown parser kind: {kind}")


def flatten_result(result: dict[str, Any], source: str, classification_name: str, stage: str, analysis_class: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    context = result.get("context") if isinstance(result.get("context"), dict) else {}
    for name, metric in result.get("metrics", {}).items():
        if not isinstance(metric, dict): continue
        rows.append({
            "metric": name, "value": metric.get("value"), "unit": metric.get("unit", ""), "parse_status": metric.get("status", "UNKNOWN"),
            "stage": stage, "report_type": result.get("report_type", ""), "analysis": result.get("analysis", ""),
            "scenario": context.get("scenario", ""), "mode": context.get("mode", ""), "corner": context.get("corner", ""), "path_group": context.get("path_group", ""),
            "source": source, "evidence": metric.get("evidence", []), "classification": classification_name, "analysis_classification": analysis_class,
        })
    for scenario_result in result.get("scenarios", []):
        if isinstance(scenario_result, dict):
            rows.extend(flatten_result(scenario_result, source, classification_name, stage, analysis_class))
    return rows


def build_stage(root: Path, stage: str) -> dict[str, Any]:
    if stage not in STAGES: raise ValueError(f"unknown stage: {stage}")
    cfg = STAGES[stage]
    class_name, signoff_qualified, mock_scenario = classification(root)
    runtime = runtime_record(root, cfg["runtime"])
    identity = provenance_identity(root)
    analysis_class = "MOCK" if class_name == "MOCK" else ("SIGNOFF_CANDIDATE" if stage == "signoff" else "IMPLEMENTATION")
    metrics: list[dict[str, Any]] = []; sources: list[dict[str, Any]] = []
    for kind, rel, analysis in cfg["sources"]:
        path = root / rel
        if not path.is_file():
            sources.append({"path": rel, "kind": kind, "analysis": analysis, "exists": False, "parse_status": "NOT_RUN"})
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        result = parse_source(kind, text, analysis)
        sources.append({"path": rel, "kind": kind, "analysis": analysis, "exists": True, "parse_status": result.get("status", "UNKNOWN"), "warnings": result.get("warnings", [])})
        metrics.extend(flatten_result(result, rel, class_name, stage, analysis_class))
    status = status_record(root, cfg["status"])
    return {
        "schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(), "stage": stage,
        "classification": class_name, "signoff_qualified": signoff_qualified, "mock_scenario": mock_scenario,
        "run": {**identity, "run_id": runtime.get("flow_run_id", "")}, "tool": runtime.get("tool", ""), "runtime": runtime,
        "stage_status": status, "sources": sources, "metrics": metrics,
        "notes": ["Parsed metrics are evidence only; SIGNOFF_CANDIDATE does not assert signoff qualification.", "Missing metrics remain absent/None rather than zero."],
    }


def build_all(root: Path, stages: list[str] | None = None) -> dict[str, Any]:
    chosen = stages or list(STAGES)
    payloads = {stage: build_stage(root, stage) for stage in chosen}
    class_name, signoff_qualified, mock_scenario = classification(root)
    return {
        "schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(), "classification": class_name,
        "signoff_qualified": signoff_qualified, "mock_scenario": mock_scenario, "run": provenance_identity(root),
        "stages": payloads, "metric_count": sum(len(x["metrics"]) for x in payloads.values()),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build normalized ASIC stage metrics sidecar JSON.")
    ap.add_argument("--root", default=str(ROOT)); ap.add_argument("--out", default=""); ap.add_argument("--stage", action="append", choices=sorted(STAGES))
    args = ap.parse_args(); root = Path(args.root).resolve(); out = Path(args.out).resolve() if args.out else root / "reports" / "metrics"
    try: payload = build_all(root, args.stage)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}"); return 2
    out.mkdir(parents=True, exist_ok=True)
    for stage, data in payload["stages"].items(): atomic_json(out / f"{stage}.json", data)
    atomic_json(out / "all_metrics.json", payload)
    print(f"STAGE_METRICS={out / 'all_metrics.json'} metrics={payload['metric_count']} classification={payload['classification']}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
