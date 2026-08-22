#!/usr/bin/env python3
from __future__ import annotations
import csv, json, re
from pathlib import Path
from report_utils import text, first_float, first_int, slack_from_timing, status_file, metric_fmt
ROOT=Path(__file__).resolve().parents[1]
STAGES={
 'Synthesis': ('synthesis','reports/synthesis/qor.rpt','reports/synthesis/timing_min.rpt','reports/synthesis/area.rpt','reports/synthesis/power.rpt'),
 'Floorplan': ('floorplan','reports/floorplan/qor.rpt','reports/floorplan/hold.rpt','reports/floorplan/utilization.rpt',''),
 'Placement': ('placement','reports/placement/qor.rpt','reports/placement/hold.rpt','reports/placement/utilization.rpt',''),
 'Pre-CTS': ('pre_cts','reports/pre_cts/qor.rpt','reports/pre_cts/hold.rpt','reports/pre_cts/utilization.rpt',''),
 'Post-CTS': ('cts','reports/post_cts/qor.rpt','reports/post_cts/hold.rpt','reports/post_cts/utilization.rpt',''),
 'Post-CTS-Opt': ('post_cts_opt','reports/post_cts_opt/qor.rpt','reports/post_cts_opt/hold.rpt','reports/post_cts_opt/utilization.rpt',''),
 'Route': ('route','reports/route/qor.rpt','reports/route/hold.rpt','reports/route/utilization.rpt',''),
 'Post-Route': ('post_route','reports/post_route/qor.rpt','reports/post_route/hold.rpt','reports/post_route/utilization.rpt',''),
 'Signoff': ('signoff','reports/signoff/summary.rpt','reports/signoff/hold.rpt','','reports/power/vectorless_power.rpt')}

def parse_qor(path):
    s=text(ROOT/path) if path else ''
    return (first_float([r'Critical Path Slack\s*[:=]?\s*(-?[\d.]+)',r'WNS\s*[:=]?\s*(-?[\d.]+)',r'Worst Negative Slack\s*[:=]?\s*(-?[\d.]+)'],s),
            first_float([r'Total Negative Slack\s*[:=]?\s*(-?[\d.]+)',r'TNS\s*[:=]?\s*(-?[\d.]+)'],s),
            first_int([r'No\. of Violating Paths\s*[:=]?\s*(\d+)',r'violating\s+(?:paths|endpoints)\s*[:=]?\s*(\d+)'],s))

def parse_area(path):
    s=text(ROOT/path) if path else ''
    return (first_float([r'Total cell area\s*:\s*([\d.eE+-]+)',r'Utilization\s*(?:Ratio|%)?\s*[:=]?\s*([\d.]+)'],s),
            first_int([r'Number of cells\s*:\s*(\d+)',r'Cell Count\s*[:=]\s*(\d+)'],s))

def parse_power(path):
    s=text(ROOT/path) if path else ''
    return first_float([r'Total Power\s*[:=]?\s*([\d.eE+-]+)'],s)
rows=[]
for name,(status_key,qor,hold,area,power) in STAGES.items():
    wns,tns,viol=parse_qor(qor)
    hs=slack_from_timing(text(ROOT/hold)) if hold else None
    ar,cells=parse_area(area)
    pw=parse_power(power)
    rows.append({'Stage':name,'WNS':wns,'TNS':tns,'Setup Violations':viol,'Worst Hold Slack':hs,
                 'Hold Violations':None,'Area':ar,'Utilization':None,'Cell Count':cells,'Buffer Count':None,
                 'Inverter Count':None,'Power':pw,'Congestion':None,'DRC':None,'Runtime':None,
                 'Status':status_file(ROOT,status_key)})
out=ROOT/'reports'/'summary'; out.mkdir(parents=True,exist_ok=True)
cols=list(rows[0])
with (out/'qor_summary.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(rows)
(out/'qor_summary.json').write_text(json.dumps(rows,indent=2))
md=['# ASIC QoR Summary','', '| '+' | '.join(cols)+' |','| '+' | '.join(['---']*len(cols))+' |']
for r in rows: md.append('| '+' | '.join(metric_fmt(r[c]) for c in cols)+' |')
(out/'qor_summary.md').write_text('\n'.join(md)+'\n')
print(out/'qor_summary.md')
