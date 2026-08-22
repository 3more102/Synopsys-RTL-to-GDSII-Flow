#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT_NAME="${PROJECT_NAME:-MIPS_16}"
VCS="${VCS:-vcs}"
: "${TB_TOP:?Set TB_TOP to the testbench top module}"
: "${TB_FILES:?Set TB_FILES to the testbench source file list/string}"
: "${SIM_LIB_FILES:?Set SIM_LIB_FILES to standard-cell simulation model files}"
NET="$ROOT/netlist/${PROJECT_NAME}_postroute.v"
SDF="$ROOT/sdf/${PROJECT_NAME}_postroute.sdf"
[[ -f "$NET" ]] || { echo "Missing post-route netlist: $NET" >&2; exit 2; }
[[ -f "$SDF" ]] || { echo "Missing post-route SDF: $SDF" >&2; exit 2; }
command -v "$VCS" >/dev/null || { echo "VCS not found: $VCS" >&2; exit 2; }
mkdir -p "$ROOT/work/gls" "$ROOT/logs"
cd "$ROOT/work/gls"
: "${SDF_ANNOTATE_SCOPE:?Set SDF_ANNOTATE_SCOPE, e.g. tb.dut}"
"$VCS" -full64 -sverilog -timescale=1ns/1ps $TB_FILES "$NET" $SIM_LIB_FILES \
  -top "$TB_TOP" -o simv 2>&1 | tee "$ROOT/logs/gls_compile_$(date +%Y%m%d_%H%M%S).log"
echo "Compile complete. Annotate $SDF onto $SDF_ANNOTATE_SCOPE from the testbench with \$sdf_annotate, then run ./simv."
