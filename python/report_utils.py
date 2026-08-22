#!/usr/bin/env python3
from __future__ import annotations
import re
from pathlib import Path

def text(path):
    p=Path(path)
    return p.read_text(errors='ignore') if p.is_file() else ''

def first_float(patterns, s):
    for pat in patterns:
        m=re.search(pat,s,re.I|re.M)
        if m:
            try: return float(m.group(1))
            except ValueError: pass
    return None

def first_int(patterns, s):
    v=first_float(patterns,s)
    return int(v) if v is not None else None

def slack_from_timing(s):
    vals=[]
    for m in re.finditer(r'\bslack\s*(?:\([^)]*\))?\s*[:=]?\s*(-?\d+(?:\.\d+)?)',s,re.I):
        try: vals.append(float(m.group(1)))
        except ValueError: pass
    return min(vals) if vals else None

def metric_fmt(v):
    if v is None: return 'N/A'
    if isinstance(v,float): return f'{v:.4f}'
    return str(v)

def status_file(root, stage):
    p=Path(root)/'reports'/'status'/f'{stage}.status'
    if not p.is_file(): return 'UNKNOWN'
    m=re.search(r'^status=(.+)$',p.read_text(errors='ignore'),re.M)
    return m.group(1).strip() if m else 'UNKNOWN'
