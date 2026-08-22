#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

stages=(env lint synth formal presta init floorplan powerplan place prects cts postcts route postroute closure outputs extract signoff power drc gds lvs reports final verify snapshot)
FLOW_RUN_ID="${FLOW_RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
export FLOW_RUN_ID

dry_run=0
list_only=0

normalize(){
  case "$1" in
    environment|check) echo env;; synthesis) echo synth;; pre-sta|sta) echo presta;;
    placement) echo place;; pre-cts) echo prects;; post-cts) echo postcts;;
    post-route) echo postroute;; extraction) echo extract;; physical-verification|pv) echo drc;;
    *) echo "$1";;
  esac
}

idx(){
  local x="$(normalize "$1")" i
  for i in "${!stages[@]}"; do
    [[ "${stages[$i]}" == "$x" ]] && { echo "$i"; return 0; }
  done
  return 1
}

run(){
  local s="$(normalize "$1")"
  echo "========== $s [FLOW_RUN_ID=$FLOW_RUN_ID] =========="
  if (( dry_run )); then
    make --no-print-directory -n "$s"
  else
    make --no-print-directory "$s"
  fi
}

usage(){
  cat <<USAGE
Usage:
  ./run_flow.sh all
  ./run_flow.sh <stage>
  ./run_flow.sh --from <stage> [--to <stage>] [--dry-run]
  ./run_flow.sh --resume <stage> [--to <stage>] [--dry-run]
  ./run_flow.sh --list

FLOW_RUN_ID=$FLOW_RUN_ID
USAGE
}

if [[ $# -eq 0 ]]; then
  usage
  exit 2
fi

if [[ "$1" == "--list" ]]; then
  printf '%s\n' "${stages[@]}"
  exit 0
fi

if [[ "$1" == "all" ]]; then
  for s in "${stages[@]}"; do run "$s"; done
  exit 0
fi

if [[ "$1" != --* ]]; then
  if [[ "$1" =~ ^(release|static|config-check|test-parsers)$ ]]; then run "$1"; exit 0; fi
  idx "$1" >/dev/null || { echo "Unknown stage: $1" >&2; usage >&2; exit 2; }
  run "$1"
  exit 0
fi

from=0
to=$((${#stages[@]}-1))
while [[ $# -gt 0 ]]; do
  case "$1" in
    --resume|--from)
      [[ $# -ge 2 ]] || { echo "Missing stage after $1" >&2; exit 2; }
      from=$(idx "$2") || { echo "Unknown stage: $2" >&2; exit 2; }
      shift 2;;
    --to)
      [[ $# -ge 2 ]] || { echo "Missing stage after --to" >&2; exit 2; }
      to=$(idx "$2") || { echo "Unknown stage: $2" >&2; exit 2; }
      shift 2;;
    --dry-run)
      dry_run=1
      shift;;
    --help|-h)
      usage
      exit 0;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2;;
  esac
done

(( from <= to )) || { echo "--from stage occurs after --to stage" >&2; exit 2; }
for ((i=from; i<=to; i++)); do run "${stages[$i]}"; done
