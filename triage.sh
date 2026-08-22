#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <log-file> [--stage <name>] [--tool <tool>] [--exit-code <code>]" >&2
  exit 2
fi

log="$1"
shift
exec python3 python/triage_failure.py --log "$log" "$@"
