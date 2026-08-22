#!/usr/bin/env bash
# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : invalidate_after_eco.sh
# Description : Invalidates only downstream Make stamps after an accepted physical ECO.
# =============================================================================
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
active_file="$ROOT/checkpoints/active_physical_block.txt"
[[ -f "$active_file" ]] || { echo "No promoted ECO block; downstream stamps unchanged."; exit 0; }
active="$(tr -d '[:space:]' < "$active_file")"
[[ "$active" == eco_* ]] || { echo "Active block '$active' is not an ECO-promoted block; downstream stamps unchanged."; exit 0; }
# Remove only explicit generated marker files under PROJECT_ROOT. Source/configuration files are never touched.
markers=(
  "$ROOT/reports/status/fillers.status"
  "$ROOT/reports/status/final_outputs.status"
  "$ROOT/checkpoints/extraction/extraction.status"
  "$ROOT/checkpoints/signoff/signoff.status"
  "$ROOT/reports/status/power.status"
  "$ROOT/reports/status/drc.status"
  "$ROOT/checkpoints/final/gds.status"
  "$ROOT/reports/status/lvs.status"
  "$ROOT/reports/summary/qor_summary.json"
  "$ROOT/final_delivery/MANIFEST.txt"
)
for f in "${markers[@]}"; do
  case "$(realpath -m "$f")" in "$ROOT"/*) rm -f -- "$f" ;; *) echo "Refusing out-of-root marker: $f" >&2; exit 2;; esac
done
echo "Accepted ECO '$active': downstream extraction/signoff/delivery stamps invalidated for required regeneration."
