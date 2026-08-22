#!/usr/bin/env python3
"""Verify the generated release package without claiming foundry signoff.

Default mode proves core flow artifacts + formal/setup/hold evidence.
STRICT_SIGNOFF=1 additionally requires DRC and LVS status=PASS.
REQUIRE_SDF=1 promotes SDF from advisory to required.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from report_utils import status_record

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'config' / 'stage_contracts.json'
OUT = ROOT / 'reports' / 'summary'
STATUS_DIR = ROOT / 'reports' / 'status'
PROJECT = os.environ.get('PROJECT_NAME', 'MIPS_16')
STRICT = os.environ.get('STRICT_SIGNOFF', '0').lower() in {'1', 'true', 'yes', 'on'}
REQUIRE_SDF = os.environ.get('REQUIRE_SDF', '0').lower() in {'1', 'true', 'yes', 'on'}


def expand(value: str) -> str:
    return value.replace('${PROJECT_NAME}', PROJECT)


def check_artifact(item):
    rel = expand(item['path'])
    p = ROOT / rel
    size = p.stat().st_size if p.is_file() else 0
    ok = p.is_file() and size >= int(item.get('min_bytes', 1))
    return {'path': rel, 'ok': ok, 'size': size, 'reason': item.get('reason', '')}


def check_status(stage, allowed):
    rec = status_record(ROOT, stage)
    return {
        'stage': stage,
        'status': rec['status'],
        'allowed': allowed,
        'ok': rec['status'] in allowed,
        'detail': rec.get('detail', ''),
    }


contract = json.loads(CONTRACT.read_text())
required_artifacts = [check_artifact(x) for x in contract['required_artifacts']]
optional_artifacts = [check_artifact(x) for x in contract.get('optional_artifacts', [])]
if REQUIRE_SDF:
    for item in optional_artifacts:
        if item['path'].endswith('.sdf'):
            required_artifacts.append(item)

required_status = [check_status(stage, allowed) for stage, allowed in contract['required_status'].items()]
advisory_status = [check_status(stage, allowed) for stage, allowed in contract.get('advisory_status', {}).items()]
strict_status = [check_status(stage, allowed) for stage, allowed in contract.get('strict_signoff_status', {}).items()] if STRICT else []

failures = []
for item in required_artifacts:
    if not item['ok']:
        failures.append(f"missing/empty artifact: {item['path']}")
for item in required_status + strict_status:
    if not item['ok']:
        failures.append(f"status {item['stage']}={item['status']} not in {item['allowed']}")

result = {
    'project': PROJECT,
    'mode': 'STRICT_SIGNOFF' if STRICT else 'FLOW_RELEASE',
    'require_sdf': REQUIRE_SDF,
    'result': 'PASS' if not failures else 'FAIL',
    'required_artifacts': required_artifacts,
    'optional_artifacts': optional_artifacts,
    'required_status': required_status,
    'advisory_status': advisory_status,
    'strict_status': strict_status,
    'failures': failures,
    'note': 'FLOW_RELEASE PASS is not a foundry tapeout signoff. STRICT_SIGNOFF additionally requires DRC/LVS PASS evidence.'
}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'release_verification.json').write_text(json.dumps(result, indent=2) + '\n')

lines = [
    '# Release Verification', '',
    f"- Project: `{PROJECT}`",
    f"- Mode: **{result['mode']}**",
    f"- Result: **{result['result']}**",
    f"- Require SDF: `{REQUIRE_SDF}`",
    '', '## Required artifacts',
]
for x in required_artifacts:
    lines.append(f"- [{'x' if x['ok'] else ' '}] `{x['path']}` — {x['size']} bytes — {x['reason']}")
lines += ['', '## Required status evidence']
for x in required_status + strict_status:
    lines.append(f"- [{'x' if x['ok'] else ' '}] `{x['stage']}` = **{x['status']}** (allowed: {', '.join(x['allowed'])})")
lines += ['', '## Advisory status']
for x in advisory_status:
    lines.append(f"- `{x['stage']}` = **{x['status']}**")
lines += ['', '> FLOW_RELEASE PASS is not equivalent to foundry tapeout signoff. Use `STRICT_SIGNOFF=1` only after qualified DRC/LVS integration.']
if failures:
    lines += ['', '## Failures'] + [f'- {x}' for x in failures]
(OUT / 'release_verification.md').write_text('\n'.join(lines) + '\n')

STATUS_DIR.mkdir(parents=True, exist_ok=True)
(STATUS_DIR / 'release_verify.status').write_text(
    f"stage=release_verify\nstatus={result['result']}\n"
    f"detail=mode={result['mode']}; failures={len(failures)}\n"
)
print(f"RELEASE_VERIFICATION={result['result']} mode={result['mode']} failures={len(failures)}")
if failures:
    for failure in failures:
        print(f"ERROR: {failure}")
raise SystemExit(1 if failures else 0)
