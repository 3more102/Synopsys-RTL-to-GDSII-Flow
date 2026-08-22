#!/usr/bin/env bash
# =============================================================================
# Project     : MIPS_16 ASIC Flow
# Stage       : External StarRC extraction
# Tool        : Synopsys StarRC (StarXtract)
# Description : Validates and executes a project/PDK-qualified StarRC command file.
# =============================================================================
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STARRC="${STARRC:-StarXtract}"
CMD="${STARRC_CMD_FILE:-}"
[[ -n "$CMD" ]] || { echo "ERROR: set STARRC_CMD_FILE to a qualified StarRC command file." >&2; exit 2; }
[[ -f "$CMD" ]] || { echo "ERROR: StarRC command file not found: $CMD" >&2; exit 2; }
command -v "$STARRC" >/dev/null 2>&1 || { echo "ERROR: StarRC executable not found: $STARRC" >&2; exit 2; }
mkdir -p "$ROOT/logs" "$ROOT/extracted"
"$STARRC" -clean "$CMD" 2>&1 | tee "$ROOT/logs/starrc_$(date +%Y%m%d_%H%M%S).log"
