#!/usr/bin/env bash
# Static repository validation that requires no Synopsys license or PDK.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0

say() { printf '[static] %s\n' "$*"; }
err() { printf '[static][ERROR] %s\n' "$*" >&2; fail=1; }

say "Checking shell syntax"
while IFS= read -r -d '' f; do
  bash -n "$f" || err "bash syntax failed: $f"
done < <(find . -type f -name '*.sh' -not -path './.git/*' -print0)

say "Checking Python syntax without creating pyc files"
python3 - <<'PY'
from pathlib import Path
bad=[]
for p in sorted(Path('.').rglob('*.py')):
    if '.git' in p.parts:
        continue
    try:
        compile(p.read_text(encoding='utf-8'), str(p), 'exec')
    except Exception as exc:
        bad.append((p, exc))
if bad:
    for p, exc in bad:
        print(f'PYTHON_SYNTAX_ERROR {p}: {exc}')
    raise SystemExit(1)
print('python syntax: PASS')
PY

say "Checking JSON configuration"
python3 -m json.tool config/stage_contracts.json >/dev/null

say "Checking Makefile parse"
make --no-print-directory -s help >/dev/null

say "Checking Tcl/SDC lexical completeness"
if command -v tclsh >/dev/null 2>&1; then
  while IFS= read -r -d '' f; do
    if ! TCL_FILE="$f" tclsh <<'TCL'
set p $::env(TCL_FILE)
set h [open $p r]
set s [read $h]
close $h
if {![info complete $s]} {
  puts stderr "incomplete Tcl syntax: $p"
  exit 1
}
TCL
    then
      err "Tcl/SDC lexical completeness failed: $f"
    fi
  done < <(find config constraints scripts power_intent -type f \( -name '*.tcl' -o -name '*.sdc' -o -name '*.upf' \) -print0)
else
  say "tclsh unavailable: Tcl lexical check skipped"
fi

say "Checking unresolved merge markers"
if grep -R -n -E '^(<<<<<<<|=======|>>>>>>>)' --exclude-dir=.git -- . >/tmp/asic_merge_markers.$$ 2>/dev/null; then
  cat /tmp/asic_merge_markers.$$ >&2
  err "unresolved merge markers found"
fi
rm -f /tmp/asic_merge_markers.$$

if (( fail )); then
  say "STATIC VALIDATION: FAIL"
  exit 1
fi
say "STATIC VALIDATION: PASS"
