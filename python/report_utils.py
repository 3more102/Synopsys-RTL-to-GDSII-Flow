#!/usr/bin/env python3
from __future__ import annotations
import json
import re
from pathlib import Path


def text(path):
    p = Path(path)
    return p.read_text(errors='ignore') if p.is_file() else ''


def first_float(patterns, s):
    for pat in patterns:
        m = re.search(pat, s, re.I | re.M)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
    return None


def first_int(patterns, s):
    v = first_float(patterns, s)
    return int(v) if v is not None else None


def slack_from_timing(s):
    vals = []
    for m in re.finditer(r'\bslack\s*(?:\([^)]*\))?\s*[:=]?\s*(-?\d+(?:\.\d+)?)', s, re.I):
        try:
            vals.append(float(m.group(1)))
        except ValueError:
            pass
    return min(vals) if vals else None


def violated_path_count(s):
    return len(re.findall(r'\bslack\s*\(VIOLATED\)', s, re.I))


def metric_fmt(v):
    if v is None:
        return 'N/A'
    if isinstance(v, float):
        return f'{v:.4f}'
    return str(v)


def status_record(root, stage):
    p = Path(root) / 'reports' / 'status' / f'{stage}.status'
    if not p.is_file():
        return {'status': 'UNKNOWN', 'detail': 'status file missing', 'path': str(p)}
    body = p.read_text(errors='ignore')
    def field(name, default=''):
        m = re.search(rf'^{re.escape(name)}=(.*)$', body, re.M)
        return m.group(1).strip() if m else default
    return {
        'status': field('status', 'UNKNOWN'),
        'detail': field('detail', ''),
        'time': field('time', ''),
        'path': str(p),
    }


def status_file(root, stage):
    return status_record(root, stage)['status']


def latest_runtime(root, stage):
    p = Path(root) / 'reports' / 'runtime' / f'{stage}.latest.json'
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text())
        value = data.get('duration_seconds')
        return int(value) if value is not None else None
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
