#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${PYTHON:-python3}"

# Refresh provenance immediately before snapshot creation so the archived run
# has a current content/methodology/technology/execution identity.
"$PYTHON" "$ROOT/python/build_provenance.py"

stamp="$(date +%Y-%m-%d_%H%M%S)"
run="$ROOT/runs/${stamp}_asic_run"
mkdir -p "$run"
for d in config logs reports results checkpoints; do [[ -e "$ROOT/$d" ]] && cp -a "$ROOT/$d" "$run/"; done
{
  echo "date=$(date -Is)"; echo "hostname=$(hostname)"; echo "user=$(id -un)";
  if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "git_commit=$(git -C "$ROOT" rev-parse HEAD)"
    echo "git_dirty=$(git -C "$ROOT" status --porcelain | grep -q . && echo YES || echo NO)"
  else
    echo "git_commit=N/A"; echo "git_dirty=N/A"
  fi
  if [[ -f "$ROOT/reports/provenance/run_provenance.json" ]]; then
    digest=$("$PYTHON" - <<'PY' "$ROOT/reports/provenance/run_provenance.json"
import json,sys
print(json.load(open(sys.argv[1])).get('provenance_digest','UNKNOWN'))
PY
)
    echo "provenance_digest=$digest"
  fi
  for t in "${DC_SHELL:-dc_shell}" "${ICC2_SHELL:-icc2_shell}" "${PT_SHELL:-pt_shell}" "${FM_SHELL:-fm_shell}"; do
    if command -v "$t" >/dev/null 2>&1; then
      echo "tool=$t path=$(command -v "$t")"
      echo "version_begin=$t"
      "$t" -version </dev/null 2>&1 | head -5 || true
      echo "version_end=$t"
    else echo "tool=$t MISSING"; fi
  done
} > "$run/manifest.txt"
find "$ROOT/rtl" "$ROOT/constraints" -maxdepth 2 -type f -print0 2>/dev/null | sort -z | xargs -0 -r sha256sum > "$run/input_hashes.sha256"
echo "$run"
