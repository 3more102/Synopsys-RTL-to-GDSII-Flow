#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ $# -eq 1 ]] || { echo "Usage: $0 <stage>"; exit 2; }
exec "$ROOT/run_flow.sh" --resume "$1"
