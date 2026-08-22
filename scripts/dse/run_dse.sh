#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UTILS=(0.50 0.55 0.60 0.65 0.70)
ARS=(0.8 1.0 1.2)
: "${DSE_CLOCK_PERIODS:=10.0}"
mkdir -p "$ROOT/runs/dse"
for u in "${UTILS[@]}"; do
  for ar in "${ARS[@]}"; do
    for cp in $DSE_CLOCK_PERIODS; do
      tag="u${u}_ar${ar}_cp${cp}"
      dir="$ROOT/runs/dse/$tag"; mkdir -p "$dir"
      cat > "$dir/point.env" <<POINT
CORE_UTILIZATION=$u
CORE_ASPECT_RATIO=$ar
CLOCK_PERIOD=$cp
DSE_TAG=$tag
POINT
      printf 'PREPARED %-32s %s\n' "$tag" "$dir/point.env"
    done
  done
done
cat <<'MSG'
No EDA jobs were launched. To execute one point in an isolated workspace:
  bash scripts/dse/run_point.sh <prepared-tag>
Each point keeps its own logs/reports/results/database under runs/dse/<tag>/workspace/.
MSG
