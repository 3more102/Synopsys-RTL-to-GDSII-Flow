#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
args=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --include-current) args+=(--include-current); shift;;
    --limit) [[ $# -ge 2 ]] || { echo "ERROR: --limit requires an integer" >&2; exit 2; }; args+=(--limit "$2"); shift 2;;
    --help|-h) exec python3 python/index_run_history.py --help;;
    *) echo "ERROR: unknown option: $1" >&2; exit 2;;
  esac
done
exec python3 python/index_run_history.py "${args[@]}"
