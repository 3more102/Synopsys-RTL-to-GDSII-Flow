#!/usr/bin/env python3
"""Compare current QoR summary against a baseline and enforce a JSON policy."""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rows_by_stage(path: Path):
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError(f"QoR summary must be a JSON list: {path}")
    out = {}
    for row in data:
        if isinstance(row, dict) and row.get('Stage'):
            out[str(row['Stage'])] = row
    return out


def numeric(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def evaluate_metric(stage, metric, baseline, current, rule):
    severity = str(rule.get('severity', 'fail')).lower()
    b = numeric(baseline)
    c = numeric(current)
    messages = []
    status = 'PASS'

    if c is None:
        if rule.get('require_current', False):
            return {'stage': stage, 'metric': metric, 'status': 'FAIL', 'severity': severity, 'baseline': b, 'current': c, 'messages': ['required current metric is unavailable']}
        return {'stage': stage, 'metric': metric, 'status': 'SKIP', 'severity': severity, 'baseline': b, 'current': c, 'messages': ['current metric unavailable; rule is optional']}

    if 'absolute_min' in rule and c < float(rule['absolute_min']):
        messages.append(f"current {c:g} < absolute_min {float(rule['absolute_min']):g}")
    if 'absolute_max' in rule and c > float(rule['absolute_max']):
        messages.append(f"current {c:g} > absolute_max {float(rule['absolute_max']):g}")

    need_baseline = bool(rule.get('require_baseline', False))
    has_regression_limit = 'max_regression_abs' in rule or 'max_regression_percent' in rule
    if b is None:
        if need_baseline:
            messages.append('required baseline metric is unavailable')
        elif has_regression_limit:
            messages.append('baseline unavailable; regression comparison skipped')
    elif has_regression_limit:
        direction = rule.get('direction')
        if direction not in {'higher', 'lower'}:
            messages.append(f"invalid direction '{direction}'")
        else:
            regression_abs = (b - c) if direction == 'higher' else (c - b)
            if 'max_regression_abs' in rule and regression_abs > float(rule['max_regression_abs']) + 1e-12:
                messages.append(f"absolute regression {regression_abs:g} > allowed {float(rule['max_regression_abs']):g}")
            if 'max_regression_percent' in rule:
                if abs(b) < 1e-15:
                    if regression_abs > 0:
                        messages.append('percentage regression undefined because baseline is zero and current is worse')
                else:
                    pct = 100.0 * regression_abs / abs(b)
                    if pct > float(rule['max_regression_percent']) + 1e-12:
                        messages.append(f"regression {pct:.3f}% > allowed {float(rule['max_regression_percent']):g}%")

    hard_problem = any(
        ('unavailable' in m and ('required' in m or 'baseline' in m and need_baseline))
        or m.startswith('current ')
        or m.startswith('absolute regression')
        or m.startswith('regression ')
        or m.startswith('percentage regression')
        or m.startswith('invalid direction')
        for m in messages
    )
    if hard_problem:
        status = 'WARN' if severity == 'warn' else 'FAIL'
    elif messages:
        status = 'PASS'
    return {'stage': stage, 'metric': metric, 'status': status, 'severity': severity, 'baseline': b, 'current': c, 'messages': messages}


def run(policy, baseline_rows, current_rows):
    results = []
    for stage, rules in policy.get('stages', {}).items():
        brow = baseline_rows.get(stage, {})
        crow = current_rows.get(stage, {})
        for metric, rule in rules.items():
            results.append(evaluate_metric(stage, metric, brow.get(metric), crow.get(metric), rule))
    failures = [r for r in results if r['status'] == 'FAIL']
    warnings = [r for r in results if r['status'] == 'WARN']
    return results, failures, warnings


def main():
    ap = argparse.ArgumentParser(description='Evidence-driven QoR regression gate')
    ap.add_argument('--baseline', default=os.environ.get('QOR_BASELINE', ''), help='baseline qor_summary.json; or set QOR_BASELINE')
    ap.add_argument('--current', default=str(ROOT / 'reports' / 'summary' / 'qor_summary.json'))
    ap.add_argument('--policy', default=str(ROOT / 'config' / 'qor_policy.json'))
    args = ap.parse_args()
    if not args.baseline:
        ap.error('baseline is required: use --baseline <qor_summary.json> or QOR_BASELINE=...')

    baseline_path = Path(args.baseline).expanduser().resolve()
    current_path = Path(args.current).expanduser().resolve()
    policy_path = Path(args.policy).expanduser().resolve()
    for p in (baseline_path, current_path, policy_path):
        if not p.is_file():
            raise SystemExit(f'ERROR: required file not found: {p}')

    policy = json.loads(policy_path.read_text())
    results, failures, warnings = run(policy, rows_by_stage(baseline_path), rows_by_stage(current_path))
    out = ROOT / 'reports' / 'summary'
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        'result': 'FAIL' if failures else 'PASS',
        'baseline': str(baseline_path),
        'current': str(current_path),
        'policy': str(policy_path),
        'failure_count': len(failures),
        'warning_count': len(warnings),
        'checks': results,
    }
    (out / 'qor_regression.json').write_text(json.dumps(payload, indent=2) + '\n')
    lines = [
        '# QoR Regression Gate', '',
        f"- Result: **{payload['result']}**",
        f"- Baseline: `{baseline_path}`",
        f"- Current: `{current_path}`",
        f"- Policy: `{policy_path}`",
        f"- Failures: **{len(failures)}**",
        f"- Warnings: **{len(warnings)}**",
        '', '| Stage | Metric | Baseline | Current | Status | Details |',
        '| --- | --- | ---: | ---: | --- | --- |',
    ]
    for r in results:
        detail = '; '.join(r['messages']) or 'within policy'
        lines.append(f"| {r['stage']} | {r['metric']} | {r['baseline'] if r['baseline'] is not None else 'N/A'} | {r['current'] if r['current'] is not None else 'N/A'} | {r['status']} | {detail} |")
    (out / 'qor_regression.md').write_text('\n'.join(lines) + '\n')
    print(f"QOR_REGRESSION={payload['result']} failures={len(failures)} warnings={len(warnings)}")
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
