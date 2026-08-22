#!/usr/bin/env python3
import json, datetime, os
from pathlib import Path
from report_utils import status_file
ROOT=Path(__file__).resolve().parents[1]
PROJECT=os.getenv('PROJECT_NAME','MIPS_16')
TOP=os.getenv('TOP_MODULE','mips_16')
TECH=os.getenv('TECHNOLOGY','SAED90nm')
summary=ROOT/'reports'/'summary'/'qor_summary.json'
rows=json.loads(summary.read_text()) if summary.is_file() else []
final=rows[-1] if rows else {}
def exists(rel): return 'GENERATED' if (ROOT/rel).is_file() else 'MISSING'
status={k:status_file(ROOT,k) for k in ['lint','synthesis','formal','floorplan','placement','cts','post_route','extraction','signoff','setup_sta','hold_sta','power','drc','lvs','gds']}
lines=['# FINAL SUMMARY','',f'Date: {datetime.datetime.now().isoformat(timespec="seconds")}',
       f'Project: {PROJECT}',f'Top Module: {TOP}',f'Technology: {TECH} (configured externally)','', '## Flow Status']
for k,v in status.items(): lines.append(f'- {k}: {v}')
lines += ['', '## Final QoR']
for k in ['WNS','TNS','Worst Hold Slack','Area','Utilization','Power','Cell Count','DRC']: lines.append(f'- {k}: {final.get(k,"N/A")}')
lines += ['', '## Deliverables',
          f'- GDS: {exists(f"gds/{PROJECT}.gds")}', f'- Post-route netlist: {exists(f"netlist/{PROJECT}_postroute.v")}',
          f'- SDF: {exists(f"sdf/{PROJECT}_postroute.sdf")}', f'- SPEF: {exists(f"spef/{PROJECT}_postroute.spef")}',
          '', '## Known Limitations', '- DRC/LVS remain UNKNOWN unless a foundry-qualified runset/deck is configured and executed.',
          '- Power is vectorless or activity-based analysis, not measured silicon power.',
          '- Technology-specific layers/cells/models are intentionally never guessed.']
out=ROOT/'final_delivery'/'FINAL_SUMMARY.md'; out.parent.mkdir(parents=True,exist_ok=True); out.write_text('\n'.join(lines)+'\n'); print(out)
