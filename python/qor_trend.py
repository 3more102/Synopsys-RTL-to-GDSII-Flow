#!/usr/bin/env python3
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'reports'/'summary'/'qor_summary.json'
if not p.is_file(): raise SystemExit('Run python/generate_summary.py first.')
for r in json.loads(p.read_text()): print(f"{r['Stage']:<16} WNS={r.get('WNS','N/A')} TNS={r.get('TNS','N/A')} Hold={r.get('Worst Hold Slack','N/A')}")
