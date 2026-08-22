#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
args=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --stage) [[ $# -ge 2 ]] || { echo "ERROR: --stage requires a value" >&2; exit 2; }; args+=(--stage "$2"); shift 2;;
    --include-not-run) args+=(--include-not-run); shift;;
    --fail-on-stale) args+=(--fail-on-stale); shift;;
    --help|-h) exec python3 python/plan_rebuild.py --help;;
    *) echo "ERROR: unknown option: $1" >&2; exit 2;;
  esac
done
exec python3 python/plan_rebuild.py "${args[@]}"
