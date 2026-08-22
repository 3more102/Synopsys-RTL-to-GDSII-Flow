#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/final_delivery"
PROJECT_NAME="${PROJECT_NAME:-MIPS_16}"
PYTHON="${PYTHON:-python3}"
mkdir -p "$OUT"/{timing,power,physical,qor,logs,floorplan/reports,floorplan/screenshot}
copy_if(){ [[ -f "$1" ]] && cp -f "$1" "$2" || true; }
copy_if "$ROOT/gds/${PROJECT_NAME}.gds" "$OUT/${PROJECT_NAME}.gds"
copy_if "$ROOT/netlist/${PROJECT_NAME}_postroute.v" "$OUT/${PROJECT_NAME}_postroute.v"
copy_if "$ROOT/sdf/${PROJECT_NAME}_postroute.sdf" "$OUT/${PROJECT_NAME}_postroute.sdf"
copy_if "$ROOT/spef/${PROJECT_NAME}_postroute.spef" "$OUT/${PROJECT_NAME}_postroute.spef"
copy_if "$ROOT/results/final/${PROJECT_NAME}_final.sdc" "$OUT/${PROJECT_NAME}_final.sdc"
copy_if "$ROOT/scripts/floorplan/01_floorplan.tcl" "$OUT/floorplan/floorplan.tcl"
cp -a "$ROOT/reports/signoff/." "$OUT/timing/" 2>/dev/null || true
cp -a "$ROOT/reports/power/." "$OUT/power/" 2>/dev/null || true
cp -a "$ROOT/reports/physical/." "$OUT/physical/" 2>/dev/null || true
cp -a "$ROOT/reports/summary/." "$OUT/qor/" 2>/dev/null || true
cp -a "$ROOT/reports/floorplan/." "$OUT/floorplan/reports/" 2>/dev/null || true
cp -a "$ROOT/screenshots/." "$OUT/floorplan/screenshot/" 2>/dev/null || true
cp -a "$ROOT/logs/." "$OUT/logs/" 2>/dev/null || true
"$PYTHON" "$ROOT/python/final_summary.py"
(
 cd "$OUT"
 find . -type f ! -name checksums.txt -print0 | sort -z | xargs -0 -r sha256sum > checksums.txt
)
manifest="$OUT/MANIFEST.txt"
: > "$manifest"
for f in "${PROJECT_NAME}.gds" "${PROJECT_NAME}_postroute.v" "${PROJECT_NAME}_postroute.sdf" "${PROJECT_NAME}_postroute.spef" "${PROJECT_NAME}_final.sdc"; do
  [[ -f "$OUT/$f" ]] && echo "[GENERATED] $f" >> "$manifest" || echo "[MISSING]   $f" >> "$manifest"
done
for s in lint synthesis formal floorplan placement cts post_route extraction signoff setup_sta hold_sta power drc lvs gds; do
  sf="$ROOT/reports/status/$s.status"
  if [[ -f "$sf" ]]; then st=$(awk -F= '/^status=/{print $2}' "$sf" | tail -1); else st=UNKNOWN; fi
  printf '[%-9s] %s\n' "$st" "$s" >> "$manifest"
done
echo "Final deliverables collected in $OUT"
