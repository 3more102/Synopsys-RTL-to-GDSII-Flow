#!/usr/bin/env python3
import argparse, json
from report_utils import text, slack_from_timing, first_float, first_int

def parse(path):
    s=text(path)
    return {'worst_slack': slack_from_timing(s),
            'tns': first_float([r'Total Negative Slack\s*[:=]?\s*(-?\d+(?:\.\d+)?)',r'TNS\s*[:=]?\s*(-?\d+(?:\.\d+)?)'],s),
            'violations': first_int([r'No\. of Violating Paths\s*[:=]?\s*(\d+)',r'violating\s+(?:paths|endpoints)\s*[:=]?\s*(\d+)'],s)}
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('report'); a=ap.parse_args(); print(json.dumps(parse(a.report),indent=2))
