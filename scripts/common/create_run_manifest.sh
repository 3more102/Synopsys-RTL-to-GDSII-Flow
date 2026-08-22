#!/usr/bin/env bash
# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : create_run_manifest.sh
# Description : Records reproducibility metadata without fabricating tool results.
# =============================================================================
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/reports/run_manifest.txt"
mkdir -p "$(dirname "$OUT")"
{
  echo "Project: ${PROJECT_NAME:-MIPS_16}"
  echo "Top module: ${TOP_MODULE:-mips_16}"
  echo "Technology: ${TECHNOLOGY:-SAED90nm}"
  echo "Date: $(date -Is)"
  echo "Hostname: $(hostname)"
  echo "User: $(id -un)"
  echo "Project root: $ROOT"
  if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Git commit: $(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo UNKNOWN)"
    echo "Git dirty: $(git -C "$ROOT" status --porcelain | grep -q . && echo YES || echo NO)"
  else
    echo "Git commit: N/A"
    echo "Git dirty: N/A"
  fi
  echo
  echo "[Tool executables]"
  for pair in \
    "DC_SHELL:${DC_SHELL:-dc_shell}" \
    "ICC2_SHELL:${ICC2_SHELL:-icc2_shell}" \
    "PT_SHELL:${PT_SHELL:-pt_shell}" \
    "FM_SHELL:${FM_SHELL:-fm_shell}" \
    "STARRC:${STARRC:-StarXtract}" \
    "ICV:${ICV:-icv}"; do
    var="${pair%%:*}"; exe="${pair#*:}"
    if command -v "$exe" >/dev/null 2>&1; then
      echo "$var=$exe ($(command -v "$exe"))"
    else
      echo "$var=$exe (MISSING)"
    fi
  done
  echo
  echo "[Configured machine/PDK environment]"
  for var in TARGET_LIBRARY LINK_LIBRARIES STD_CELL_NDM TECH_FILE TLU_PLUS_MAX TLU_PLUS_MIN TLU_PLUS_MAP GDS_LAYER_MAP \
             MIN_ROUTING_LAYER MAX_ROUTING_LAYER PG_RING_H_LAYER PG_RING_V_LAYER PG_MESH_H_LAYER PG_MESH_V_LAYER PG_STD_CELL_RAIL_LAYER; do
    printf '%s=%s\n' "$var" "${!var:-}"
  done
  echo
  echo "[Configuration file hashes]"
  find "$ROOT/config" -maxdepth 1 -type f -name '*.tcl' -print0 | sort -z | xargs -0 -r sha256sum
  echo
  echo "[RTL hashes]"
  find "$ROOT/rtl" -maxdepth 2 -type f \( -name '*.v' -o -name '*.sv' \) -print0 | sort -z | xargs -0 -r sha256sum
  echo
  echo "[SDC hashes]"
  find "$ROOT/constraints" -maxdepth 1 -type f -name '*.sdc' -print0 | sort -z | xargs -0 -r sha256sum
} > "$OUT"
echo "$OUT"
