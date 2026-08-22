#!/usr/bin/env python3
import argparse, json
from report_utils import text, first_float, first_int

def parse(path):
    s=text(path)
    return {'total_cell_area': first_float([r'Total cell area\s*:\s*([\d.eE+-]+)',r'Cell Area\s*[:=]\s*([\d.eE+-]+)'],s),
            'combinational_area': first_float([r'Combinational area\s*:\s*([\d.eE+-]+)'],s),
            'sequential_area': first_float([r'Noncombinational area\s*:\s*([\d.eE+-]+)',r'Sequential area\s*:\s*([\d.eE+-]+)'],s),
            'cell_count': first_int([r'Number of cells\s*:\s*(\d+)',r'Cell Count\s*[:=]\s*(\d+)'],s)}
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('report'); a=ap.parse_args(); print(json.dumps(parse(a.report),indent=2))
