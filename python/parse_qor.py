#!/usr/bin/env python3
import argparse, json
from pathlib import Path
from report_utils import text, first_float, first_int, slack_from_timing

def parse(path):
    s=text(path)
    return {
      'WNS': first_float([r'Critical Path Slack\s*[:=]?\s*(-?\d+(?:\.\d+)?)',r'WNS\s*[:=]?\s*(-?\d+(?:\.\d+)?)',r'Worst Negative Slack\s*[:=]?\s*(-?\d+(?:\.\d+)?)'],s),
      'TNS': first_float([r'Total Negative Slack\s*[:=]?\s*(-?\d+(?:\.\d+)?)',r'TNS\s*[:=]?\s*(-?\d+(?:\.\d+)?)'],s),
      'Violating Paths': first_int([r'No\. of Violating Paths\s*[:=]?\s*(\d+)',r'violating\s+(?:paths|endpoints)\s*[:=]?\s*(\d+)'],s),
      'Worst Slack From Timing': slack_from_timing(s)
    }
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('report'); a=ap.parse_args(); print(json.dumps(parse(a.report),indent=2))
