#!/usr/bin/env python3
import argparse, json
from pathlib import Path
METRICS=['WNS','TNS','Area','Power','Utilization','Cell Count','DRC']
def load(run):
    p=Path(run)/'reports'/'summary'/'qor_summary.json'
    if not p.is_file(): raise SystemExit(f'Missing {p}')
    rows=json.loads(p.read_text()); return rows[-1] if rows else {}
ap=argparse.ArgumentParser(); ap.add_argument('run_a'); ap.add_argument('run_b'); a=ap.parse_args()
A,B=load(a.run_a),load(a.run_b)
print(f"{'Metric':<20}{'Run A':>15}{'Run B':>15}{'Difference':>15}")
for m in METRICS:
    va,vb=A.get(m),B.get(m)
    diff=(vb-va) if isinstance(va,(int,float)) and isinstance(vb,(int,float)) else 'N/A'
    print(f"{m:<20}{str(va):>15}{str(vb):>15}{str(diff):>15}")
