#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
scenario="clean"
output=""
project="MOCK_CHIP"
force=0
validate=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --scenario) [[ $# -ge 2 ]] || { echo "ERROR: --scenario requires a value" >&2; exit 2; }; scenario="$2"; shift 2;;
    --output) [[ $# -ge 2 ]] || { echo "ERROR: --output requires a value" >&2; exit 2; }; output="$2"; shift 2;;
    --project) [[ $# -ge 2 ]] || { echo "ERROR: --project requires a value" >&2; exit 2; }; project="$2"; shift 2;;
    --force) force=1; shift;;
    --no-validate) validate=0; shift;;
    --help|-h) cat <<'EOF'
Usage: ./mock_flow.sh [--scenario clean|timing_fail|drc_fail|license_fail|missing_artifact]
                      [--output DIR] [--project NAME] [--force] [--no-validate]

Generates deterministic MOCK-only ASIC reports/artifacts without launching Synopsys tools.
All outputs are explicitly marked MOCK DATA - NOT SIGNOFF and stay under work/mock_runs by default.
EOF
      exit 0;;
    *) echo "ERROR: unknown option: $1" >&2; exit 2;;
  esac
done
[[ -n "$output" ]] || output="work/mock_runs/$scenario"
cmd=(python3 python/run_mock_flow.py --scenario "$scenario" --output "$output" --project "$project")
(( force )) && cmd+=(--force)
"${cmd[@]}"
if (( validate )); then
  python3 python/validate_mock_flow.py "$output"
fi
