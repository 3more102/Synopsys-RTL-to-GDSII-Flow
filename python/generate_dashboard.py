#!/usr/bin/env python3
from __future__ import annotations
import html, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SUMMARY=ROOT/'reports'/'summary'/'qor_summary.json'
OUT=ROOT/'reports'/'summary'/'dashboard.html'

def load(path, default):
    try:return json.loads(path.read_text())
    except Exception:return default

def esc(x):return html.escape('N/A' if x is None else str(x))
def status_class(s):
    s=str(s or 'UNKNOWN').upper()
    return 'pass' if s=='PASS' else 'fail' if s=='FAIL' else 'warn'
rows=load(SUMMARY,[])
release=load(ROOT/'reports'/'summary'/'release_verification.json',{})
reg=load(ROOT/'reports'/'summary'/'qor_regression.json',{})
plan=load(ROOT/'reports'/'summary'/'rebuild_plan.json',{})
headers=['Stage','WNS','TNS','Setup Violations','Worst Hold Slack','Hold Violations','Area','Utilization','Power','Congestion','DRC','Runtime','Status']
body=[]
for r in rows:
    cells=[]
    for h in headers:
        v=r.get(h)
        cells.append(f'<td><span class="pill {status_class(v)}">{esc(v)}</span></td>' if h=='Status' else f'<td>{esc(v)}</td>')
    body.append('<tr>'+''.join(cells)+'</tr>')
def card(title,value,kind='warn'):
    return f'<div class="card"><div class="label">{esc(title)}</div><div class="value {kind}">{esc(value)}</div></div>'
release_state=release.get('overall_status',release.get('status','UNKNOWN'))
reg_state=reg.get('overall_status',reg.get('status','N/A'))
rebuild='YES' if plan.get('rebuild_required') else ('NO' if plan else 'N/A')
cards=''.join([card('Release verification',release_state,status_class(release_state)),card('QoR regression gate',reg_state,status_class(reg_state)),card('Rebuild required',rebuild,'fail' if rebuild=='YES' else 'pass' if rebuild=='NO' else 'warn'),card('Earliest rebuild stage',plan.get('earliest_rebuild_stage') or 'none','warn')])
css="""body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#0f172a;color:#e2e8f0}main{max-width:1500px;margin:auto;padding:28px}h1{margin:0 0 6px}.muted{color:#94a3b8}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:24px 0}.card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:16px}.label{font-size:12px;color:#94a3b8;text-transform:uppercase}.value{font-size:22px;font-weight:700;margin-top:6px}.pass{color:#4ade80}.fail{color:#fb7185}.warn{color:#fbbf24}.table{overflow:auto;background:#111827;border:1px solid #334155;border-radius:12px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:10px 12px;border-bottom:1px solid #243244;text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}th{position:sticky;top:0;background:#1e293b}.pill{font-weight:700}.foot{margin-top:18px;font-size:12px;color:#94a3b8}code{color:#bae6fd}"""
doc=f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ASIC QoR Dashboard</title><style>{css}</style></head><body><main><h1>ASIC QoR Dashboard</h1><div class="muted">Evidence-driven summary. Missing metrics are shown as N/A; this page does not manufacture signoff results.</div><div class="cards">{cards}</div><div class="table"><table><thead><tr>{''.join(f'<th>{esc(h)}</th>' for h in headers)}</tr></thead><tbody>{''.join(body) if body else '<tr><td colspan="13">No QoR summary generated yet.</td></tr>'}</tbody></table></div><div class="foot">Sources: <code>reports/summary/qor_summary.json</code>, release verification, QoR regression gate, and rebuild planner outputs.</div></main></body></html>'''
OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(doc);print(OUT)
