#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
if [[ -f reports/summary/qor_summary.json ]]; then :; else
  echo "WARNING: reports/summary/qor_summary.json not found; dashboard will show N/A until reports are generated." >&2
fi
python3 python/generate_dashboard.py
