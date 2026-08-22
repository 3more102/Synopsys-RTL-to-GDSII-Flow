#!/usr/bin/env python3
"""Index normalized stage metrics across archived ASIC runs.

The ledger preserves stage/scenario/corner/classification so later comparisons
can reject incompatible evidence instead of comparing unrelated scalar summaries.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS = ROOT / "runs"
DEFAULT_OUT = ROOT / "reports" / "history"

COLUMNS = [
    "run", "date", "git_commit", "branch", "project", "top", "provenance_digest",
    "stage", "tool", "scenario", "mode", "corner", "path_group", "metric", "value", "unit",
    "parse_status", "classification", "analysis_classification", "source", "comparison_key",
]


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def read_manifest(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line:
                key, value = line.split("=", 1); out.setdefault(key.strip(), value.strip())
    except OSError:
        pass
    return out


def metric_rows(payload: dict[str, Any], run_name: str, date: str = "") -> list[dict[str, Any]]:
    stages = payload.get("stages")
    if not isinstance(stages, dict): return []
    root_run = payload.get("run") if isinstance(payload.get("run"), dict) else {}
    rows: list[dict[str, Any]] = []
    for stage, stage_payload in stages.items():
        if not isinstance(stage_payload, dict): continue
        run = stage_payload.get("run") if isinstance(stage_payload.get("run"), dict) else root_run
        for metric in stage_payload.get("metrics", []):
            if not isinstance(metric, dict): continue
            row = {
                "run": run_name,
                "date": date,
                "git_commit": run.get("git_commit", root_run.get("git_commit", "")),
                "branch": run.get("branch", root_run.get("branch", "")),
                "project": run.get("project", root_run.get("project", "")),
                "top": run.get("top", root_run.get("top", "")),
                "provenance_digest": run.get("provenance_digest", root_run.get("provenance_digest", "")),
                "stage": stage,
                "tool": stage_payload.get("tool", ""),
                "scenario": metric.get("scenario", ""), "mode": metric.get("mode", ""), "corner": metric.get("corner", ""), "path_group": metric.get("path_group", ""),
                "metric": metric.get("metric", ""), "value": metric.get("value"), "unit": metric.get("unit", ""),
                "parse_status": metric.get("parse_status", "UNKNOWN"),
                "classification": metric.get("classification", stage_payload.get("classification", payload.get("classification", "UNKNOWN"))),
                "analysis_classification": metric.get("analysis_classification", ""), "source": metric.get("source", ""),
            }
            row["comparison_key"] = "|".join(str(row[k]) for k in ("project", "top", "stage", "scenario", "mode", "corner", "metric", "unit", "classification", "analysis_classification"))
            rows.append(row)
    return rows


def rows_from_run(run_dir: Path) -> list[dict[str, Any]]:
    payload = read_json(run_dir / "reports" / "metrics" / "all_metrics.json")
    if not payload: return []
    manifest = read_manifest(run_dir / "manifest.txt")
    return metric_rows(payload, run_dir.name, manifest.get("date", ""))


def current_rows(root: Path) -> list[dict[str, Any]]:
    payload = read_json(root / "reports" / "metrics" / "all_metrics.json")
    return metric_rows(payload, "CURRENT", "") if payload else []


def build_history(runs_dir: Path, include_current_root: Path | None = None, limit: int = 0) -> list[dict[str, Any]]:
    dirs = sorted([p for p in runs_dir.glob("*") if p.is_dir()]) if runs_dir.is_dir() else []
    if limit > 0: dirs = dirs[-limit:]
    rows: list[dict[str, Any]] = []
    for run in dirs: rows.extend(rows_from_run(run))
    if include_current_root is not None: rows.extend(current_rows(include_current_root))
    rows.sort(key=lambda r: (r["date"], r["run"], r["stage"], r["scenario"], r["corner"], r["metric"], r["source"]))
    return rows


def write_outputs(rows: list[dict[str, Any]], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "metric_history.json").write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out / "metric_history.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows: handle.write(json.dumps(row, sort_keys=True) + "\n")
    with (out / "metric_history.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS); writer.writeheader(); writer.writerows({k: row.get(k) for k in COLUMNS} for row in rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Index normalized ASIC metrics across archived runs.")
    ap.add_argument("--root", default=str(ROOT)); ap.add_argument("--runs", default=""); ap.add_argument("--out", default=""); ap.add_argument("--include-current", action="store_true"); ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(); root = Path(args.root).resolve(); runs = Path(args.runs).resolve() if args.runs else root / "runs"; out = Path(args.out).resolve() if args.out else root / "reports" / "history"
    rows = build_history(runs, root if args.include_current else None, args.limit); write_outputs(rows, out)
    print(f"METRIC_HISTORY={out / 'metric_history.jsonl'} rows={len(rows)}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
