#!/usr/bin/env bash
# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : run_stage.sh
# Stage       : Shared launcher
# Description : Executes one EDA Tcl stage with pipefail and reproducibility metadata.
# =============================================================================
set -euo pipefail
if [[ $# -ne 4 ]]; then
  echo "Usage: $0 <stage-name> <tool-command> <tcl-script> <log-file>" >&2
  exit 2
fi
stage="$1"; tool="$2"; script="$3"; log="$4"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p "$(dirname "$log")"
[[ -f "$script" ]] || { echo "ERROR: Tcl script not found: $script" >&2; exit 2; }
command -v "$tool" >/dev/null 2>&1 || { echo "ERROR: tool executable not found in PATH: $tool" >&2; exit 127; }
{
  echo "================================================================"
  echo "ASIC FLOW STAGE METADATA"
  echo "stage=$stage"
  echo "project=${PROJECT_NAME:-MIPS_16}"
  echo "top=${TOP_MODULE:-mips_16}"
  echo "date=$(date -Is)"
  echo "hostname=$(hostname)"
  echo "user=$(id -un)"
  echo "tool=$tool"
  echo "tool_path=$(command -v "$tool")"
  echo "script=$(realpath -m "$script")"
  echo "project_root=$ROOT"
  echo "run_directory=$(pwd)"
  if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "git_commit=$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo UNKNOWN)"
  else
    echo "git_commit=N/A"
  fi
  echo "================================================================"
  extra_args=()
  if [[ -n "${EDA_TOOL_ARGS:-}" ]]; then read -r -a extra_args <<< "$EDA_TOOL_ARGS"; fi
  "$tool" "${extra_args[@]}" -f "$script"
} 2>&1 | tee "$log"
