#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
req=("${DC_SHELL:-dc_shell}" "${ICC2_SHELL:-icc2_shell}" "${PT_SHELL:-pt_shell}" "${FM_SHELL:-fm_shell}" "${PYTHON:-python3}")
fail=0
for t in "${req[@]}"; do
  if command -v "$t" >/dev/null 2>&1; then printf 'FOUND   %-15s %s\n' "$t" "$(command -v "$t")"; else printf 'MISSING %-15s\n' "$t"; fail=1; fi
done
[[ -w "$ROOT" ]] || { echo "Project root is not writable: $ROOT"; fail=1; }
df -h "$ROOT" | tail -1
exit "$fail"
