#!/usr/bin/env python3
from pathlib import Path
import re
from report_utils import text, first_float, slack_from_timing
ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'reports'/'status'; STATUS.mkdir(parents=True,exist_ok=True)
summary=text(ROOT/'reports'/'signoff'/'summary.rpt')
setup_report=text(ROOT/'reports'/'signoff'/'setup.rpt')
hold_report=text(ROOT/'reports'/'signoff'/'hold.rpt')

def write(name,status,detail):
    (STATUS/f'{name}.status').write_text(f'stage={name}\nstatus={status}\ndetail={detail}\n')
setup_wns=first_float([r'Setup\s+WNS\s*[:=]?\s*(-?[\d.]+)',r'WNS\s*[:=]?\s*(-?[\d.]+)'],summary)
setup_tns=first_float([r'Setup\s+TNS\s*[:=]?\s*(-?[\d.]+)',r'TNS\s*[:=]?\s*(-?[\d.]+)'],summary)
if setup_wns is None: setup_wns=slack_from_timing(setup_report)
hold_wns=first_float([r'Hold\s+WNS\s*[:=]?\s*(-?[\d.]+)',r'Hold.*?Worst.*?Slack\s*[:=]?\s*(-?[\d.]+)'],summary)
hold_tns=first_float([r'Hold\s+TNS\s*[:=]?\s*(-?[\d.]+)'],summary)
if hold_wns is None: hold_wns=slack_from_timing(hold_report)
if setup_wns is None or setup_tns is None:
    write('setup_sta','UNKNOWN',f'Could not prove both WNS and TNS from signoff reports; WNS={setup_wns} TNS={setup_tns}')
elif setup_wns >= 0 and setup_tns >= 0:
    write('setup_sta','PASS',f'WNS={setup_wns} TNS={setup_tns}')
else:
    write('setup_sta','FAIL',f'WNS={setup_wns} TNS={setup_tns}')
viol_hold=len(re.findall(r'slack\s*\(VIOLATED\)',hold_report,re.I))
if hold_wns is None:
    write('hold_sta','UNKNOWN','Worst hold slack could not be parsed.')
elif hold_tns is not None:
    write('hold_sta','PASS' if hold_wns>=0 and hold_tns>=0 else 'FAIL',f'WNS={hold_wns} TNS={hold_tns}')
elif hold_wns >= 0 and viol_hold == 0:
    write('hold_sta','PASS',f'Worst hold slack={hold_wns}; no VIOLATED paths in detailed hold report.')
else:
    write('hold_sta','FAIL',f'Worst hold slack={hold_wns}; violated_paths_seen={viol_hold}')
print((STATUS/'setup_sta.status').read_text().strip())
print((STATUS/'hold_sta.status').read_text().strip())
