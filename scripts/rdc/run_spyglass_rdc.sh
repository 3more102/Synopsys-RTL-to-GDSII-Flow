#!/usr/bin/env bash
set -euo pipefail
SPYGLASS="${SPYGLASS:-spyglass}"
PRJ="${SPYGLASS_RDC_PROJECT:-}"
GOAL="${SPYGLASS_RDC_GOAL:-}"
[[ -n "$PRJ" && -f "$PRJ" ]] || { echo "Set SPYGLASS_RDC_PROJECT to a reviewed SpyGlass project file." >&2; exit 2; }
[[ -n "$GOAL" ]] || { echo "Set SPYGLASS_RDC_GOAL to the RDC goal shown by your installed methodology (use -showgoals)." >&2; exit 2; }
command -v "$SPYGLASS" >/dev/null || { echo "SpyGlass executable not found: $SPYGLASS" >&2; exit 2; }
"$SPYGLASS" -batch -project "$PRJ" -goal "$GOAL"
