#!/usr/bin/env python3
"""Compare normalized ASIC metric sets with strict comparability checks."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "metric_regression_policy.json"
DEFAULT_CURRENT = ROOT / "reports" / "metrics" / "all_metrics.json"
DEFAULT_OUT = ROOT / "reports" / "summary" / "metric_regression.json"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict): raise ValueError(f"expected JSON object: {path}")
    return data


def finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool): return None
    try: number = float(value)
    except (TypeError, ValueError): return None
    return number if math.isfinite(number) else None


def rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    root_run = payload.get("run") if isinstance(payload.get("run"), dict) else {}
    stages = payload.get("stages") if isinstance(payload.get("stages"), dict) else {}
    for stage, sp in stages.items():
        if not isinstance(sp, dict): continue
        run = sp.get("run") if isinstance(sp.get("run"), dict) else root_run
        for metric in sp.get("metrics", []):
            if not isinstance(metric, dict): continue
            out.append({
                **metric,
                "stage": stage,
                "project": run.get("project", root_run.get("project", "")),
                "top": run.get("top", root_run.get("top", "")),
                "provenance_digest": run.get("provenance_digest", root_run.get("provenance_digest", "")),
            })
    return out


def key(row: dict[str, Any]) -> tuple[str, ...]:
    fields = ("project", "top", "stage", "scenario", "mode", "corner", "path_group", "metric", "unit", "classification", "analysis_classification", "source")
    return tuple(str(row.get(field, "")) for field in fields)


def index(payload: dict[str, Any]) -> tuple[dict[tuple[str, ...], dict[str, Any]], set[tuple[str, ...]]]:
    result: dict[tuple[str, ...], dict[str, Any]] = {}; duplicates: set[tuple[str, ...]] = set()
    for row in rows(payload):
        k = key(row)
        if k in result: duplicates.add(k)
        else: result[k] = row
    return result, duplicates


def evaluate_rule(current: float, baseline: float, rule: dict[str, Any]) -> tuple[str, float, float | None, list[str]]:
    direction = rule.get("direction")
    if direction not in {"higher", "lower"}: return "FAIL", 0.0, None, [f"invalid direction {direction!r}"]
    regression = baseline - current if direction == "higher" else current - baseline
    pct = None if abs(baseline) < 1e-15 else 100.0 * regression / abs(baseline)
    problems: list[str] = []
    if "absolute_min" in rule and current < float(rule["absolute_min"]): problems.append(f"current {current:g} < absolute_min {float(rule['absolute_min']):g}")
    if "absolute_max" in rule and current > float(rule["absolute_max"]): problems.append(f"current {current:g} > absolute_max {float(rule['absolute_max']):g}")
    if "max_regression_abs" in rule and regression > float(rule["max_regression_abs"]) + 1e-12: problems.append(f"absolute regression {regression:g} > {float(rule['max_regression_abs']):g}")
    if "max_regression_percent" in rule:
        allowed = float(rule["max_regression_percent"])
        if pct is None:
            if regression > 0: problems.append("percentage regression undefined because baseline is zero and current is worse")
        elif pct > allowed + 1e-12: problems.append(f"regression {pct:.3f}% > {allowed:g}%")
    if not problems: return "PASS", regression, pct, []
    return ("WARN" if str(rule.get("severity", "fail")).lower() == "warn" else "FAIL"), regression, pct, problems


def compare(current: dict[str, Any], baseline: dict[str, Any] | None, policy: dict[str, Any]) -> dict[str, Any]:
    if policy.get("schema_version") != 1: raise ValueError("unsupported metric regression policy schema")
    current_rows = rows(current)
    if baseline is None:
        return {"schema_version": 1, "status": "NO_BASELINE", "checks": [], "failure_count": 0, "warning_count": 0, "not_comparable_count": 0}
    bidx, bdup = index(baseline); checks: list[dict[str, Any]] = []
    rules = policy.get("metrics", {})
    for crow in current_rows:
        metric_name = str(crow.get("metric", "")); rule = rules.get(metric_name)
        if not isinstance(rule, dict): continue
        identity = key(crow); cvalue = finite(crow.get("value"))
        base = bidx.get(identity)
        record = {"metric": metric_name, "stage": crow.get("stage"), "scenario": crow.get("scenario", ""), "corner": crow.get("corner", ""), "source": crow.get("source", ""), "classification": crow.get("classification", ""), "baseline": None, "current": cvalue, "unit": crow.get("unit", ""), "status": "PASS", "messages": []}
        if identity in bdup:
            record.update(status="NOT_COMPARABLE", messages=["baseline contains duplicate rows for the exact comparison identity"]); checks.append(record); continue
        if base is None:
            record.update(status="NOT_COMPARABLE", messages=["no compatible baseline row: design/top/stage/scenario/corner/unit/classification/source must match"]); checks.append(record); continue
        bvalue = finite(base.get("value")); record["baseline"] = bvalue
        if cvalue is None or bvalue is None:
            record.update(status="NOT_COMPARABLE", messages=["current or baseline metric is non-numeric/unavailable"]); checks.append(record); continue
        status, delta, pct, messages = evaluate_rule(cvalue, bvalue, rule)
        record.update(status=status, regression=delta, regression_percent=pct, messages=messages); checks.append(record)
    failures = [x for x in checks if x["status"] == "FAIL"]; warnings = [x for x in checks if x["status"] == "WARN"]; nc = [x for x in checks if x["status"] == "NOT_COMPARABLE"]
    if failures: overall = "FAIL"
    elif warnings: overall = "WARN"
    elif checks and len(nc) == len(checks): overall = "NOT_COMPARABLE"
    else: overall = "PASS"
    return {"schema_version": 1, "status": overall, "failure_count": len(failures), "warning_count": len(warnings), "not_comparable_count": len(nc), "checks": checks}


def markdown(payload: dict[str, Any]) -> str:
    lines = ["# Normalized QoR Regression", "", f"- Status: **{payload['status']}**", f"- Failures: **{payload.get('failure_count', 0)}**", f"- Warnings: **{payload.get('warning_count', 0)}**", f"- Not comparable: **{payload.get('not_comparable_count', 0)}**", "", "| Stage | Metric | Scenario | Corner | Baseline | Current | Unit | Status | Details |", "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |"]
    for row in payload.get("checks", []):
        detail = "; ".join(row.get("messages", [])) or "within policy"
        lines.append(f"| {row.get('stage','')} | {row.get('metric','')} | {row.get('scenario','')} | {row.get('corner','')} | {row.get('baseline') if row.get('baseline') is not None else 'N/A'} | {row.get('current') if row.get('current') is not None else 'N/A'} | {row.get('unit','')} | {row.get('status','')} | {detail} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Comparability-aware normalized QoR regression gate")
    ap.add_argument("--current", default=str(DEFAULT_CURRENT)); ap.add_argument("--baseline", default=""); ap.add_argument("--policy", default=str(DEFAULT_POLICY)); ap.add_argument("--out", default=str(DEFAULT_OUT)); ap.add_argument("--require-baseline", action="store_true")
    args = ap.parse_args(); current_path = Path(args.current).resolve(); policy_path = Path(args.policy).resolve(); out = Path(args.out).resolve()
    try:
        current = load_json(current_path); policy = load_json(policy_path); baseline = load_json(Path(args.baseline).resolve()) if args.baseline else None
        payload = compare(current, baseline, policy)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}"); return 2
    payload.update({"current": str(current_path), "baseline": str(Path(args.baseline).resolve()) if args.baseline else "", "policy": str(policy_path)})
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"); out.with_suffix(".md").write_text(markdown(payload), encoding="utf-8")
    print(f"METRIC_REGRESSION={payload['status']} failures={payload.get('failure_count',0)} warnings={payload.get('warning_count',0)} not_comparable={payload.get('not_comparable_count',0)}")
    if payload["status"] == "FAIL": return 1
    if args.require_baseline and payload["status"] == "NO_BASELINE": return 3
    return 0


if __name__ == "__main__": raise SystemExit(main())
