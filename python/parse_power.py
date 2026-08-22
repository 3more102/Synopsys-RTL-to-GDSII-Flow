#!/usr/bin/env python3
import argparse, json
from report_utils import text, first_float

def parse(path):
    s=text(path)
    return {'internal_power': first_float([r'Internal Power\s*[:=]?\s*([\d.eE+-]+)'],s),
            'switching_power': first_float([r'Switching Power\s*[:=]?\s*([\d.eE+-]+)'],s),
            'leakage_power': first_float([r'Cell Leakage Power\s*=\s*([\d.eE+-]+)',r'Leakage Power\s*[:=]?\s*([\d.eE+-]+)'],s),
            'total_power': first_float([r'Total Power\s*[:=]?\s*([\d.eE+-]+)'],s)}
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('report'); a=ap.parse_args(); print(json.dumps(parse(a.report),indent=2))
