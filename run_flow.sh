#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

stages=(env lint synth formal presta init floorplan powerplan place prects cts postcts route postroute closure outputs extract signoff power drc gds lvs reports final verify snapshot)
FLOW_RUN_ID="${FLOW_RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
export FLOW_RUN_ID

dry_run=0
archive_database=0

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
      echo "Use './run_flow.sh --plan' to review the dependency-aware rebuild plan." >&2
      echo "Use './run_flow.sh --execute-plan' only after reviewing it." >&2
      echo "Bypass only with FLOW_FRESHNESS_CHECK=0." >&2
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

validate_flow_model(){
  python3 "$ROOT/python/validate_flow_model.py" --json-out reports/summary/flow_model_validation.json
}

make_rebuild_plan(){
  local target="${1:-}" args
  args=(python3 "$ROOT/python/plan_rebuild.py" --include-not-run)
  if [[ -n "$target" ]]; then args+=(--stage "$target"); fi
  "${args[@]}"
}

execute_rebuild_plan(){
  local target="${1:-}" plan="$ROOT/reports/summary/rebuild_plan.json" apply_args targets t
  validate_flow_model
  make_rebuild_plan "$target"

  mapfile -t targets < <(python3 - "$plan" <<'PY'
import json,sys
p=json.load(open(sys.argv[1]))
for target in p.get('execution_targets',[]):
    print(target)
PY
)
  if [[ ${#targets[@]} -eq 0 ]]; then
    echo "Rebuild plan is empty; all required existing evidence is fresh."
    return 0
  fi

  echo "Planned Make targets: ${targets[*]}"
  if (( dry_run )); then
    echo "DRY RUN: no evidence/database will be moved and no EDA tools will run."
    for t in "${targets[@]}"; do echo "make --no-print-directory $t"; done
    return 0
  fi

  apply_args=(python3 "$ROOT/python/apply_rebuild_plan.py" --plan "$plan" --apply)
  if (( archive_database )); then apply_args+=(--archive-database); fi
  "${apply_args[@]}"

  for t in "${targets[@]}"; do
    echo "========== planned target: $t [FLOW_RUN_ID=$FLOW_RUN_ID] =========="
    make --no-print-directory "$t"
  done
}

usage(){ cat <<USAGE
Usage:
  ./run_flow.sh all
  ./run_flow.sh <stage>
  ./run_flow.sh --from <stage> [--to <stage>] [--dry-run]
  ./run_flow.sh --resume <stage> [--to <stage>] [--dry-run]
  ./run_flow.sh --plan [stage]
  ./run_flow.sh --execute-plan [stage] [--dry-run] [--archive-database]
  ./run_flow.sh --list

Rebuild planning:
  --plan              Validate the flow model and show stale + never-run stages.
  --execute-plan      Archive stale evidence, then run only planned Make targets.
  --archive-database  Required when the plan must rebuild icc2_init and database/ is non-empty.
                      The database is moved to runs/stale_database_archive/; it is never deleted.

Quality/reproducibility commands also accepted directly:
  doctor static config-check test-parsers sdc-audit mmmc-audit mmmc-signoff-audit
  capabilities fingerprint freshness provenance compare-provenance release-manifest qor-gate release

FLOW_RUN_ID=$FLOW_RUN_ID
USAGE
}

if [[ $# -eq 0 ]]; then usage; exit 2; fi
if [[ "$1" == "--list" ]]; then printf '%s\n' "${stages[@]}"; exit 0; fi

if [[ "$1" == "--plan" ]]; then
  shift
  target=""
  if [[ $# -gt 0 && "$1" != --* ]]; then target="$1"; shift; fi
  [[ $# -eq 0 ]] || { echo "Unexpected arguments after --plan" >&2; exit 2; }
  validate_flow_model
  make_rebuild_plan "$target"
  exit 0
fi

if [[ "$1" == "--execute-plan" ]]; then
  shift
  target=""
  if [[ $# -gt 0 && "$1" != --* ]]; then target="$1"; shift; fi
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) dry_run=1;;
      --archive-database) archive_database=1;;
      *) echo "Unknown --execute-plan option: $1" >&2; usage >&2; exit 2;;
    esac
    shift
  done
  execute_rebuild_plan "$target"
  exit 0
fi

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
