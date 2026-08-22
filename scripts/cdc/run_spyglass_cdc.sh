#!/usr/bin/env bash
# Batch SpyGlass CDC launcher. Goal name is explicit because methodology goal paths vary by release/project.
set -euo pipefail
SPYGLASS="${SPYGLASS:-spyglass}"
PRJ="${SPYGLASS_CDC_PROJECT:-}"
GOAL="${SPYGLASS_CDC_GOAL:-}"
[[ -n "$PRJ" && -f "$PRJ" ]] || { echo "Set SPYGLASS_CDC_PROJECT to a reviewed SpyGlass project file." >&2; exit 2; }
[[ -n "$GOAL" ]] || { echo "Set SPYGLASS_CDC_GOAL to the CDC goal shown by your installed methodology (use -showgoals)." >&2; exit 2; }
command -v "$SPYGLASS" >/dev/null || { echo "SpyGlass executable not found: $SPYGLASS" >&2; exit 2; }
"$SPYGLASS" -batch -project "$PRJ" -goal "$GOAL"
