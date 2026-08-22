#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/final_delivery"
PROJECT_NAME="${PROJECT_NAME:-MIPS_16}"
PYTHON="${PYTHON:-python3}"
mkdir -p "$OUT"/{timing,power,physical,qor,history,tools,logs,provenance,floorplan/reports,floorplan/screenshot}
copy_if(){ [[ -f "$1" ]] && cp -f "$1" "$2" || true; }

# Capture reproducibility evidence immediately before packaging so the release
# contains the identity of the inputs/methodology/technology used at delivery time.
"$PYTHON" "$ROOT/python/build_provenance.py"

# Refresh per-artifact lineage after run provenance exists. The normal final
# package records missing required artifacts as WARNING evidence rather than
# inventing them; release/CI can invoke --strict-required as an explicit gate.
if [[ -f "$ROOT/python/build_artifact_provenance.py" ]]; then
  "$PYTHON" "$ROOT/python/build_artifact_provenance.py"
fi

# Refresh advisory rebuild evidence and the self-contained dashboard before
# copying reports into final_delivery. The rebuild planner is evidence-only and
# never launches a licensed EDA tool. A stale plan is recorded rather than hidden;
# final release acceptance remains governed by verify_artifacts/QoR policy.
if [[ -f "$ROOT/python/plan_rebuild.py" ]]; then
  "$PYTHON" "$ROOT/python/plan_rebuild.py" || true
fi
if [[ -f "$ROOT/python/generate_dashboard.py" ]]; then
  "$PYTHON" "$ROOT/python/generate_dashboard.py"
fi

# Build historical trend evidence from archived run snapshots and the current
# report set. Missing metrics remain N/A; this does not create signoff results.
if [[ -f "$ROOT/python/index_run_history.py" ]]; then
  "$PYTHON" "$ROOT/python/index_run_history.py" --include-current
fi

copy_if "$ROOT/gds/${PROJECT_NAME}.gds" "$OUT/${PROJECT_NAME}.gds"
copy_if "$ROOT/netlist/${PROJECT_NAME}_postroute.v" "$OUT/${PROJECT_NAME}_postroute.v"
copy_if "$ROOT/sdf/${PROJECT_NAME}_postroute.sdf" "$OUT/${PROJECT_NAME}_postroute.sdf"
copy_if "$ROOT/spef/${PROJECT_NAME}_postroute.spef" "$OUT/${PROJECT_NAME}_postroute.spef"
copy_if "$ROOT/results/final/${PROJECT_NAME}_final.sdc" "$OUT/${PROJECT_NAME}_final.sdc"
copy_if "$ROOT/scripts/floorplan/01_floorplan.tcl" "$OUT/floorplan/floorplan.tcl"
copy_if "$ROOT/python/verify_delivery_integrity.py" "$OUT/tools/verify_delivery_integrity.py"
copy_if "$ROOT/docs/VERIFY_DELIVERY.md" "$OUT/VERIFY_DELIVERY.md"
cp -a "$ROOT/reports/signoff/." "$OUT/timing/" 2>/dev/null || true
cp -a "$ROOT/reports/power/." "$OUT/power/" 2>/dev/null || true
cp -a "$ROOT/reports/physical/." "$OUT/physical/" 2>/dev/null || true
cp -a "$ROOT/reports/summary/." "$OUT/qor/" 2>/dev/null || true
cp -a "$ROOT/reports/history/." "$OUT/history/" 2>/dev/null || true
cp -a "$ROOT/reports/provenance/." "$OUT/provenance/" 2>/dev/null || true
cp -a "$ROOT/reports/floorplan/." "$OUT/floorplan/reports/" 2>/dev/null || true
cp -a "$ROOT/screenshots/." "$OUT/floorplan/screenshot/" 2>/dev/null || true
cp -a "$ROOT/logs/." "$OUT/logs/" 2>/dev/null || true

"$PYTHON" "$ROOT/python/final_summary.py"

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

# Build the machine-readable release manifest before checksums so the manifest
# itself is also covered by final_delivery/checksums.txt.
"$PYTHON" "$ROOT/python/build_release_manifest.py"
(
 cd "$OUT"
 find . -type f ! -name checksums.txt -print0 | sort -z | xargs -0 -r sha256sum > checksums.txt
)

# Verify the completed package after its final checksum inventory exists. The
# verification report is intentionally written outside final_delivery so it does
# not mutate the package after checksums are finalized.
"$PYTHON" "$ROOT/python/verify_delivery_integrity.py" \
  --delivery "$OUT" \
  --strict-extra \
  --report "$ROOT/reports/summary/delivery_integrity.json"

echo "Final deliverables collected in $OUT"
