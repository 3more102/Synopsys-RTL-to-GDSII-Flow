#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS = ROOT / "runs"
DEFAULT_OUT = ROOT / "reports" / "history"

METRICS = ["WNS", "TNS", "Worst Hold Slack", "Area", "Utilization", "Cell Count", "Power", "Runtime"]


def read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def read_manifest(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                data.setdefault(key.strip(), value.strip())
    except OSError:
        pass
    return data


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.upper() == "N/A":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def rows_by_stage(rows: Any) -> dict[str, dict]:
    if not isinstance(rows, list):
        return {}
    return {str(row.get("Stage")): row for row in rows if isinstance(row, dict) and row.get("Stage")}


def first_metric(stage_rows: dict[str, dict], stages: list[str], metric: str) -> Any:
    for stage in stages:
        row = stage_rows.get(stage)
        if row and row.get(metric) not in (None, "", "N/A"):
            return row.get(metric)
    return None


def total_runtime(rows: Any) -> float | None:
    if not isinstance(rows, list):
        return None
    values = [number(row.get("Runtime")) for row in rows if isinstance(row, dict)]
    nums = [v for v in values if v is not None]
    return sum(nums) if nums else None


def summarize_run(run_dir: Path) -> dict[str, Any] | None:
    summary_path = run_dir / "reports" / "summary" / "qor_summary.json"
    rows = read_json(summary_path)
    if not isinstance(rows, list):
        return None
    by_stage = rows_by_stage(rows)
    manifest = read_manifest(run_dir / "manifest.txt")
    provenance = read_json(run_dir / "reports" / "provenance" / "run_provenance.json") or {}
    verification = read_json(run_dir / "reports" / "summary" / "release_verification.json") or {}
    regression = read_json(run_dir / "reports" / "summary" / "qor_regression.json") or {}

    record: dict[str, Any] = {
        "Run": run_dir.name,
        "Date": manifest.get("date", ""),
        "Git Commit": manifest.get("git_commit", ""),
        "Git Dirty": manifest.get("git_dirty", ""),
        "Provenance": provenance.get("provenance_digest", manifest.get("provenance_digest", "")),
        "Release Status": verification.get("status", "UNKNOWN"),
        "QoR Gate": regression.get("status", "UNKNOWN"),
        "WNS": first_metric(by_stage, ["Signoff", "Post-Route", "Route"], "WNS"),
        "TNS": first_metric(by_stage, ["Signoff", "Post-Route", "Route"], "TNS"),
        "Worst Hold Slack": first_metric(by_stage, ["Signoff", "Post-Route", "Post-CTS-Opt", "Post-CTS"], "Worst Hold Slack"),
        "Area": first_metric(by_stage, ["Post-Route", "Route", "Post-CTS-Opt", "Placement", "Synthesis"], "Area"),
        "Utilization": first_metric(by_stage, ["Post-Route", "Route", "Post-CTS-Opt", "Placement", "Floorplan"], "Utilization"),
        "Cell Count": first_metric(by_stage, ["Post-Route", "Route", "Post-CTS-Opt", "Placement", "Synthesis"], "Cell Count"),
        "Power": first_metric(by_stage, ["Signoff", "Post-Route", "Route", "Synthesis"], "Power"),
        "Runtime": total_runtime(rows),
    }
    return record


def current_record(root: Path) -> dict[str, Any] | None:
    rows = read_json(root / "reports" / "summary" / "qor_summary.json")
    if not isinstance(rows, list):
        return None
    by_stage = rows_by_stage(rows)
    provenance = read_json(root / "reports" / "provenance" / "run_provenance.json") or {}
    verification = read_json(root / "reports" / "summary" / "release_verification.json") or {}
    regression = read_json(root / "reports" / "summary" / "qor_regression.json") or {}
    return {
        "Run": "CURRENT",
        "Date": "",
        "Git Commit": provenance.get("git", {}).get("commit", "") if isinstance(provenance.get("git"), dict) else "",
        "Git Dirty": provenance.get("git", {}).get("dirty", "") if isinstance(provenance.get("git"), dict) else "",
        "Provenance": provenance.get("provenance_digest", ""),
        "Release Status": verification.get("status", "UNKNOWN"),
        "QoR Gate": regression.get("status", "UNKNOWN"),
        "WNS": first_metric(by_stage, ["Signoff", "Post-Route", "Route"], "WNS"),
        "TNS": first_metric(by_stage, ["Signoff", "Post-Route", "Route"], "TNS"),
        "Worst Hold Slack": first_metric(by_stage, ["Signoff", "Post-Route", "Post-CTS-Opt", "Post-CTS"], "Worst Hold Slack"),
        "Area": first_metric(by_stage, ["Post-Route", "Route", "Post-CTS-Opt", "Placement", "Synthesis"], "Area"),
        "Utilization": first_metric(by_stage, ["Post-Route", "Route", "Post-CTS-Opt", "Placement", "Floorplan"], "Utilization"),
        "Cell Count": first_metric(by_stage, ["Post-Route", "Route", "Post-CTS-Opt", "Placement", "Synthesis"], "Cell Count"),
        "Power": first_metric(by_stage, ["Signoff", "Post-Route", "Route", "Synthesis"], "Power"),
        "Runtime": total_runtime(rows),
    }


def add_deltas(records: list[dict[str, Any]]) -> None:
    previous: dict[str, Any] | None = None
    for record in records:
        deltas: dict[str, float | None] = {}
        for metric in METRICS:
            cur = number(record.get(metric))
            prev = number(previous.get(metric)) if previous else None
            deltas[metric] = cur - prev if cur is not None and prev is not None else None
        record["Delta"] = deltas
        previous = record


def fmt(value: Any) -> str:
    if value is None or value == "":
        return "N/A"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def write_outputs(records: list[dict[str, Any]], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "run_history.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")

    columns = ["Run", "Date", "Git Commit", "Provenance", "Release Status", "QoR Gate", *METRICS]
    with (out / "run_history.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for record in records:
            writer.writerow({key: record.get(key) for key in columns})

    md = ["# ASIC Run History", "", "| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for record in records:
        md.append("| " + " | ".join(fmt(record.get(key)) for key in columns) + " |")
    (out / "run_history.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    rows_html = []
    for record in reversed(records):
        cells = "".join(f"<td>{html.escape(fmt(record.get(key)))}</td>" for key in columns)
        rows_html.append(f"<tr>{cells}</tr>")
    html_doc = f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>ASIC Run History</title><style>
body{{font-family:system-ui,-apple-system,sans-serif;margin:24px;background:#fff;color:#111}}h1{{margin-bottom:4px}}p{{color:#555}}
.wrap{{overflow:auto;border:1px solid #ddd;border-radius:8px}}table{{border-collapse:collapse;width:100%;font-size:13px;white-space:nowrap}}
th,td{{padding:8px 10px;border-bottom:1px solid #eee;text-align:right}}th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){{text-align:left}}th{{position:sticky;top:0;background:#f6f6f6}}
.note{{margin-top:16px;font-size:12px;color:#666}}
</style></head><body><h1>ASIC Run History</h1><p>{len(records)} archived/current run record(s). Values are parsed evidence; unavailable metrics remain N/A.</p>
<div class=\"wrap\"><table><thead><tr>{''.join(f'<th>{html.escape(c)}</th>' for c in columns)}</tr></thead><tbody>{''.join(rows_html)}</tbody></table></div>
<p class=\"note\">This dashboard does not replace PrimeTime, DRC/LVS, IR/EM, or foundry signoff reports.</p></body></html>"""
    (out / "run_history.html").write_text(html_doc, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Index archived ASIC run snapshots into machine-readable and HTML QoR history.")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--runs", default=str(DEFAULT_RUNS))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--include-current", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="Keep only the newest N archived runs; 0 means all.")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    runs_dir = Path(args.runs)
    if not runs_dir.is_absolute():
        runs_dir = root / runs_dir
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out

    run_dirs = sorted([p for p in runs_dir.glob("*") if p.is_dir()]) if runs_dir.is_dir() else []
    if args.limit > 0:
        run_dirs = run_dirs[-args.limit :]
    records = [record for p in run_dirs if (record := summarize_run(p)) is not None]
    if args.include_current:
        current = current_record(root)
        if current:
            records.append(current)
    add_deltas(records)
    write_outputs(records, out)
    print(out / "run_history.html")
    print(f"RUN_HISTORY_COUNT={len(records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
