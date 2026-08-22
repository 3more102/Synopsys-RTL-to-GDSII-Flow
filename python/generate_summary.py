#!/usr/bin/env python3
from __future__ import annotations
import csv
import json
import re
from pathlib import Path
from report_utils import text, first_int, slack_from_timing, violated_path_count, status_file, metric_fmt, latest_runtime
from qor_parsers import parse_qor, parse_area_util, parse_power, parse_congestion, parse_drc

ROOT = Path(__file__).resolve().parents[1]

STAGES = {
    'Synthesis':      dict(status='synthesis',   runtime='synthesis', qor='reports/synthesis/qor.rpt',        hold='reports/synthesis/timing_min.rpt',       area='reports/synthesis/area.rpt',              power='reports/synthesis/power.rpt'),
    'Floorplan':      dict(status='floorplan',   runtime='floorplan', qor='reports/floorplan/qor.rpt',        hold='reports/floorplan/hold.rpt',              area='reports/floorplan/utilization.rpt'),
    'Placement':      dict(status='placement',   runtime='placement', qor='reports/placement/qor.rpt',        hold='reports/placement/hold.rpt',              area='reports/placement/utilization.rpt',        congestion='reports/placement/congestion.rpt'),
    'Pre-CTS':        dict(status='pre_cts',     runtime='pre_cts',   qor='reports/pre_cts/qor.rpt',          hold='reports/pre_cts/hold.rpt',                area='reports/pre_cts/utilization.rpt',          congestion='reports/pre_cts/congestion.rpt'),
    'Post-CTS':       dict(status='cts',         runtime='cts',       qor='reports/post_cts/qor.rpt',         hold='reports/post_cts/hold.rpt',               area='reports/post_cts/utilization.rpt'),
    'Post-CTS-Opt':   dict(status='post_cts_opt',runtime='post_cts',  qor='reports/post_cts_opt/qor.rpt',     hold='reports/post_cts_opt/hold.rpt',           area='reports/post_cts_opt/utilization.rpt'),
    'Route':          dict(status='route',       runtime='route',     qor='reports/route/qor.rpt',            hold='reports/route/hold.rpt',                  area='reports/route/utilization.rpt',            congestion='reports/route/congestion.rpt',      drc='reports/route/route_status.rpt'),
    'Post-Route':     dict(status='post_route',  runtime='route_opt', qor='reports/post_route/qor.rpt',       hold='reports/post_route/hold.rpt',             area='reports/post_route/utilization.rpt',       congestion='reports/post_route/congestion.rpt', drc='reports/post_route/route_status.rpt'),
    'Signoff':        dict(status='signoff',     runtime='signoff',   qor='reports/signoff/summary.rpt',      hold='reports/signoff/hold.rpt',                power='reports/power/vectorless_power.rpt'),
}


def read(rel):
    return text(ROOT / rel) if rel else ''


rows = []
for name, spec in STAGES.items():
    qor_s = read(spec.get('qor', ''))
    hold_s = read(spec.get('hold', ''))
    area_s = read(spec.get('area', ''))
    power_s = read(spec.get('power', ''))
    congestion_s = read(spec.get('congestion', ''))
    drc_s = read(spec.get('drc', ''))

    wns, tns, setup_viol = parse_qor(qor_s)
    hold_wns = slack_from_timing(hold_s) if hold_s else None
    hold_viol = violated_path_count(hold_s) if hold_s else None
    area, util, cells = parse_area_util(area_s)

    rows.append({
        'Stage': name,
        'WNS': wns,
        'TNS': tns,
        'Setup Violations': setup_viol,
        'Worst Hold Slack': hold_wns,
        'Hold Violations': hold_viol,
        'Area': area,
        'Utilization': util,
        'Cell Count': cells,
        'Buffer Count': first_int([r'Buffer\s+Count\s*[:=]?\s*(\d+)'], qor_s),
        'Inverter Count': first_int([r'Inverter\s+Count\s*[:=]?\s*(\d+)'], qor_s),
        'Power': parse_power(power_s),
        'Congestion': parse_congestion(congestion_s),
        'DRC': parse_drc(drc_s),
        'Runtime': latest_runtime(ROOT, spec['runtime']),
        'Status': status_file(ROOT, spec['status']),
    })

out = ROOT / 'reports' / 'summary'
out.mkdir(parents=True, exist_ok=True)
cols = list(rows[0])
with (out / 'qor_summary.csv').open('w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
(out / 'qor_summary.json').write_text(json.dumps(rows, indent=2) + '\n')
md = ['# ASIC QoR Summary', '', '| ' + ' | '.join(cols) + ' |', '| ' + ' | '.join(['---'] * len(cols)) + ' |']
for row in rows:
    md.append('| ' + ' | '.join(metric_fmt(row[c]) for c in cols) + ' |')
(out / 'qor_summary.md').write_text('\n'.join(md) + '\n')
print(out / 'qor_summary.md')
