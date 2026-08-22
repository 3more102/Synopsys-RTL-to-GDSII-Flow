#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

stages=(env lint synth formal presta init floorplan powerplan place prects cts postcts route postroute closure outputs extract signoff power drc gds lvs reports final verify snapshot)
FLOW_RUN_ID="${FLOW_RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
export FLOW_RUN_ID

dry_run=0

normalize(){
  case "$1" in
    environment|check) echo env;; synthesis) echo synth;; pre-sta|sta) echo presta;;
    placement) echo place;; pre-cts) echo prects;; post-cts) echo postcts;;
    post-route) echo postroute;; extraction) echo extract;; physical-verification|pv) echo drc;;
    *) echo "$1";;
  esac
}

idx(){ local x="$(normalize "$1")" i; for i in "${!stages[@]}"; do [[ "${stages[$i]}" == "$x" ]] && { echo "$i"; return 0; }; done; return 1; }

stamp_for(){
  case "$1" in
    env) echo checkpoints/environment/environment.status;; lint) echo checkpoints/lint/lint.status;; synth) echo checkpoints/synthesis/synthesis.status;; formal) echo checkpoints/formal/formal.status;; presta) echo checkpoints/presta/presta.status;; init) echo checkpoints/init/init.status;; floorplan) echo checkpoints/floorplan/floorplan.status;; powerplan) echo checkpoints/powerplan/powerplan.status;; place) echo checkpoints/placement/placement.status;; prects) echo checkpoints/pre_cts/pre_cts.status;; cts) echo checkpoints/post_cts/post_cts.status;; postcts) echo checkpoints/post_cts_opt/post_cts_opt.status;; route) echo checkpoints/route/route.status;; postroute) echo checkpoints/post_route/post_route.status;; closure) echo checkpoints/final_route/final_route.status;; extract) echo checkpoints/extraction/extraction.status;; signoff) echo checkpoints/signoff/signoff.status;; gds) echo checkpoints/final/gds.status;; *) echo "";;
  esac
}

freshness_guard(){
  local s="$1" stamp rc
  [[ "${FLOW_FRESHNESS_CHECK:-1}" == "1" ]] || return 0
  [[ -f "$ROOT/python/stage_fingerprint.py" && -f "$ROOT/config/fingerprint_policy.json" ]] || return 0
  stamp="$(stamp_for "$s")"; [[ -n "$stamp" && -f "$ROOT/$stamp" ]] || return 0
  if make --no-print-directory -q "$stamp" >/dev/null 2>&1; then
    set +e; python3 "$ROOT/python/stage_fingerprint.py" check --stage "$s" --if-present --quiet; rc=$?; set -e
    if [[ $rc -eq 3 ]]; then
      echo "ERROR: stale checkpoint detected for stage '$s'." >&2
      python3 "$ROOT/python/stage_fingerprint.py" check --stage "$s" --if-present --details || true
      echo "The Make stamp is current, but environment/PDK/tool identity changed." >&2
      echo "Invalidate/rebuild deliberately; bypass only with FLOW_FRESHNESS_CHECK=0." >&2
      exit 75
    elif [[ $rc -ne 0 ]]; then
      echo "WARNING: freshness check for '$s' returned rc=$rc; continuing because no stale digest was proven." >&2
    fi
  fi
}

run(){
  local s="$(normalize "$1")"
  echo "========== $s [FLOW_RUN_ID=$FLOW_RUN_ID] =========="
  if (( ! dry_run )); then freshness_guard "$s"; fi
  if (( dry_run )); then make --no-print-directory -n "$s"; else make --no-print-directory "$s"; fi
}

usage(){ cat <<USAGE
Usage:
  ./run_flow.sh all
  ./run_flow.sh <stage>
  ./run_flow.sh --from <stage> [--to <stage>] [--dry-run]
  ./run_flow.sh --resume <stage> [--to <stage>] [--dry-run]
  ./run_flow.sh --list

Quality/reproducibility commands also accepted directly:
  doctor static config-check test-parsers sdc-audit mmmc-audit mmmc-signoff-audit
  capabilities fingerprint freshness provenance compare-provenance release-manifest qor-gate release

FLOW_RUN_ID=$FLOW_RUN_ID
USAGE
}

if [[ $# -eq 0 ]]; then usage; exit 2; fi
if [[ "$1" == "--list" ]]; then printf '%s\n' "${stages[@]}"; exit 0; fi
if [[ "$1" == "all" ]]; then for s in "${stages[@]}"; do run "$s"; done; exit 0; fi
if [[ "$1" != --* ]]; then
  if [[ "$1" =~ ^(release|static|config-check|test-parsers|qor-gate|sdc-audit|mmmc-audit|mmmc-signoff-audit|capabilities|doctor|fingerprint|freshness|provenance|compare-provenance|release-manifest)$ ]]; then run "$1"; exit 0; fi
  idx "$1" >/dev/null || { echo "Unknown stage: $1" >&2; usage >&2; exit 2; }; run "$1"; exit 0
fi
from=0; to=$((${#stages[@]}-1))
while [[ $# -gt 0 ]]; do
  case "$1" in
    --resume|--from) [[ $# -ge 2 ]] || { echo "Missing stage after $1" >&2; exit 2; }; from=$(idx "$2") || { echo "Unknown stage: $2" >&2; exit 2; }; shift 2;;
    --to) [[ $# -ge 2 ]] || { echo "Missing stage after --to" >&2; exit 2; }; to=$(idx "$2") || { echo "Unknown stage: $2" >&2; exit 2; }; shift 2;;
    --dry-run) dry_run=1; shift;;
    --help|-h) usage; exit 0;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2;;
  esac
done
(( from <= to )) || { echo "--from stage occurs after --to stage" >&2; exit 2; }
for ((i=from; i<=to; i++)); do run "${stages[$i]}"; done
