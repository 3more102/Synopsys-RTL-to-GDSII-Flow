#!/usr/bin/env python3
import argparse, json
from report_utils import text, first_float, first_int

def parse(path):
    s=text(path)
    return {'utilization': first_float([r'Utilization\s*(?:Ratio|%)?\s*[:=]?\s*([\d.]+)'],s),
            'overflow': first_float([r'(?:Total )?Overflow\s*[:=]?\s*([\d.]+)'],s),
            'drc_count': first_int([r'(?:Total )?(?:DRC|violations?)\s*(?:count)?\s*[:=]?\s*(\d+)'],s)}
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('report'); a=ap.parse_args(); print(json.dumps(parse(a.report),indent=2))
