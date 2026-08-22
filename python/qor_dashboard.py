#!/usr/bin/env python3
"""Generate concise text/Markdown/HTML dashboards from normalized QoR metrics."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

STAGE_ORDER = ["synthesis", "floorplan", "placement", "pre_cts", "cts", "post_cts_opt", "route", "post_route", "signoff", "drc", "lvs"]
PREFERRED: dict[str, list[str]] = {
    "synthesis": ["setup_wns_ns", "total_cell_area_um2", "total_w"],
    "floorplan": ["utilization_ratio", "total_cell_area_um2", "setup_wns_ns"],
    "placement": ["setup_wns_ns", "utilization_ratio", "congestion_ratio", "total_overflow"],
    "pre_cts": ["setup_wns_ns", "hold_wns_ns", "congestion_ratio"],
    "cts": ["clock_skew_ns", "network_latency_ns", "setup_wns_ns", "hold_wns_ns"],
    "post_cts_opt": ["setup_wns_ns", "hold_wns_ns", "total_cell_area_um2"],
    "route": ["setup_wns_ns", "hold_wns_ns", "drc_violations", "wire_length_um", "congestion_ratio"],
    "post_route": ["setup_wns_ns", "hold_wns_ns", "drc_violations", "wire_length_um", "congestion_ratio"],
    "signoff": ["setup_wns_ns", "setup_tns_ns", "hold_wns_ns", "hold_tns_ns", "total_w", "clock_skew_ns"],
    "drc": ["violations"], "lvs": ["mismatch_count"],
}
LABEL = {
    "setup_wns_ns": "Setup WNS", "setup_tns_ns": "Setup TNS", "setup_violations": "Setup viol",
    "hold_wns_ns": "Hold WNS", "hold_tns_ns": "Hold TNS", "hold_violations": "Hold viol",
    "total_cell_area_um2": "Cell area", "utilization_ratio": "Util", "total_w": "Power",
    "clock_skew_ns": "Skew", "network_latency_ns": "Clk latency", "drc_violations": "DRC",
    "violations": "Violations", "mismatch_count": "LVS mismatches", "wire_length_um": "Wire",
    "congestion_ratio": "Congestion", "total_overflow": "Overflow",
}


def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8")); return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError): return {}


def numeric_metric(stage: dict[str, Any], name: str) -> dict[str, Any] | None:
    matches = [m for m in stage.get("metrics", []) if isinstance(m, dict) and m.get("metric") == name and m.get("value") is not None and m.get("parse_status") in {"PARSED", "DERIVED"}]
    if not matches: return None
    # Prefer explicit summary reports over path detail when both expose the same metric.
    def rank(m: dict[str, Any]) -> tuple[int, str]:
        source = str(m.get("source", "")); score = 0
        if "summary.rpt" in source or "qor.rpt" in source: score -= 20
        if "hold.rpt" in source and name.startswith("hold_"): score -= 20
        if "clock_timing.rpt" in source and name.startswith(("clock_", "network_")): score -= 20
        return score, source
    return sorted(matches, key=rank)[0]


def fmt_metric(metric: dict[str, Any]) -> str:
    value = metric.get("value"); unit = str(metric.get("unit", ""))
    if value is None: return "N/A"
    if isinstance(value, float): text = f"{value:.6g}"
    else: text = str(value)
    if unit == "ratio": return f"{float(value) * 100:.3g}%"
    if unit == "W": return f"{float(value) * 1000:.6g} mW"
    if unit == "um^2": return f"{float(value) / 1e6:.6g} mm²"
    if unit == "um": return f"{float(value) / 1000:.6g} mm"
    if unit == "count": return text
    return f"{text} {unit}".strip()


def build_rows(metrics_payload: dict[str, Any]) -> list[dict[str, Any]]:
    stages = metrics_payload.get("stages") if isinstance(metrics_payload.get("stages"), dict) else {}
    rows: list[dict[str, Any]] = []
    for stage_name in STAGE_ORDER:
        stage = stages.get(stage_name)
        if not isinstance(stage, dict): continue
        selected = []
        for name in PREFERRED.get(stage_name, []):
            metric = numeric_metric(stage, name)
            if metric is not None:
                selected.append({"name": name, "label": LABEL.get(name, name), "display": fmt_metric(metric), "value": metric.get("value"), "unit": metric.get("unit", ""), "scenario": metric.get("scenario", ""), "corner": metric.get("corner", "")})
        status_record = stage.get("stage_status") if isinstance(stage.get("stage_status"), dict) else {}
        if selected or status_record.get("status") not in (None, "", "UNKNOWN"):
            rows.append({"stage": stage_name, "status": status_record.get("status", "UNKNOWN"), "metrics": selected, "tool": stage.get("tool", "")})
    return rows


def metadata(metrics_payload: dict[str, Any], regression: dict[str, Any]) -> dict[str, Any]:
    run = metrics_payload.get("run") if isinstance(metrics_payload.get("run"), dict) else {}
    return {
        "classification": metrics_payload.get("classification", "UNKNOWN"),
        "signoff_qualified": metrics_payload.get("signoff_qualified"),
        "project": run.get("project", ""), "top": run.get("top", ""), "commit": run.get("git_commit", ""), "branch": run.get("branch", ""),
        "regression": regression.get("status", "NO_BASELINE") if regression else "NO_BASELINE",
        "baseline": regression.get("baseline", "") if regression else "",
    }


def render_text(rows: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    lines = ["=" * 72, "ASIC FLOW QoR SUMMARY", "=" * 72]
    for row in rows:
        values = ", ".join(f"{m['label']}: {m['display']}" for m in row["metrics"])
        lines.append(f"{row['stage']:<16} {str(row['status']):<12} {values}".rstrip())
    lines.extend(["=" * 72, f"Classification: {meta['classification']}", f"Signoff qualified: {meta['signoff_qualified'] if meta['signoff_qualified'] is not None else 'NOT ASSERTED'}", f"QoR regression: {meta['regression']}", f"Project/Top: {meta['project']} / {meta['top']}", f"Commit: {meta['commit'] or 'N/A'}", f"Branch: {meta['branch'] or 'N/A'}", "Parsed metrics are evidence only; this dashboard does not replace signoff reports.", "=" * 72])
    return "\n".join(lines) + "\n"


def render_markdown(rows: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    lines = ["# ASIC Flow QoR Summary", "", f"- Classification: **{meta['classification']}**", f"- Signoff qualified: **{meta['signoff_qualified'] if meta['signoff_qualified'] is not None else 'NOT ASSERTED'}**", f"- QoR regression: **{meta['regression']}**", f"- Project / top: `{meta['project']}` / `{meta['top']}`", f"- Commit: `{meta['commit'] or 'N/A'}`", "", "| Stage | Status | Available key metrics |", "| --- | --- | --- |"]
    for row in rows:
        values = "; ".join(f"{m['label']}: {m['display']}" for m in row["metrics"]) or "N/A"
        lines.append(f"| {row['stage']} | {row['status']} | {values} |")
    lines += ["", "> Parsed metrics are evidence only. This summary does not replace PrimeTime, DRC/LVS, IR/EM, extraction, or foundry signoff evidence."]
    return "\n".join(lines) + "\n"


def render_html(rows: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    table_rows = []
    for row in rows:
        metrics = "; ".join(f"{html.escape(m['label'])}: {html.escape(m['display'])}" for m in row["metrics"]) or "N/A"
        table_rows.append(f"<tr><td>{html.escape(row['stage'])}</td><td>{html.escape(str(row['status']))}</td><td>{metrics}</td></tr>")
    cards = "".join(f"<div class='card'><small>{html.escape(k)}</small><strong>{html.escape(str(v if v not in (None, '') else 'N/A'))}</strong></div>" for k, v in (("Classification", meta["classification"]), ("Regression", meta["regression"]), ("Project", meta["project"]), ("Top", meta["top"]), ("Commit", meta["commit"])))
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>ASIC QoR Summary</title><style>body{{font-family:system-ui,sans-serif;margin:0;background:#0f172a;color:#e2e8f0}}main{{max-width:1200px;margin:auto;padding:28px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:20px 0}}.card{{background:#1e293b;padding:14px;border-radius:10px}}small{{display:block;color:#94a3b8}}strong{{display:block;margin-top:5px;overflow-wrap:anywhere}}table{{width:100%;border-collapse:collapse;background:#111827}}th,td{{padding:10px;border-bottom:1px solid #334155;text-align:left}}.note{{color:#94a3b8;font-size:12px;margin-top:16px}}</style></head><body><main><h1>ASIC Flow QoR Summary</h1><div class='cards'>{cards}</div><table><thead><tr><th>Stage</th><th>Status</th><th>Available key metrics</th></tr></thead><tbody>{''.join(table_rows) or '<tr><td colspan=3>No normalized metrics available.</td></tr>'}</tbody></table><p class='note'>Parsed metrics are evidence only. This dashboard does not replace PrimeTime, DRC/LVS, IR/EM, extraction, or foundry signoff reports.</p></main></body></html>"""


def generate(metrics_path: Path, regression_path: Path, out_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    metrics_payload = load(metrics_path); regression = load(regression_path)
    rows = build_rows(metrics_payload); meta = metadata(metrics_payload, regression)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "qor_dashboard.txt").write_text(render_text(rows, meta), encoding="utf-8")
    (out_dir / "qor_dashboard.md").write_text(render_markdown(rows, meta), encoding="utf-8")
    (out_dir / "qor_dashboard.html").write_text(render_html(rows, meta), encoding="utf-8")
    return rows, meta


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate normalized ASIC QoR dashboards.")
    ap.add_argument("--metrics", default=str(ROOT / "reports" / "metrics" / "all_metrics.json")); ap.add_argument("--regression", default=str(ROOT / "reports" / "summary" / "metric_regression.json")); ap.add_argument("--out", default=str(ROOT / "reports" / "summary"))
    args = ap.parse_args(); rows, meta = generate(Path(args.metrics), Path(args.regression), Path(args.out))
    print(f"QOR_DASHBOARD={Path(args.out) / 'qor_dashboard.html'} stages={len(rows)} classification={meta['classification']}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
