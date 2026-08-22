#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
stages=(env lint synth formal presta init floorplan powerplan place prects cts postcts route postroute closure outputs extract signoff power drc gds lvs reports final)
normalize(){
  case "$1" in
    environment|check) echo env;; synthesis) echo synth;; pre-sta|sta) echo presta;;
    placement) echo place;; pre-cts) echo prects;; post-cts) echo postcts;;
    post-route) echo postroute;; extraction) echo extract;; physical-verification|pv) echo drc;;
    *) echo "$1";;
  esac
}
idx(){ local x="$(normalize "$1")" i; for i in "${!stages[@]}"; do [[ "${stages[$i]}" == "$x" ]] && { echo "$i"; return; }; done; return 1; }
run(){ local s="$(normalize "$1")"; echo "========== $s =========="; make --no-print-directory "$s"; }
if [[ $# -eq 0 || "$1" == all ]]; then
  for s in "${stages[@]}"; do run "$s"; done
  exit 0
fi
if [[ "$1" != --* ]]; then run "$1"; exit 0; fi
from=0; to=$((${#stages[@]}-1))
while [[ $# -gt 0 ]]; do
  case "$1" in
    --resume|--from) [[ $# -ge 2 ]] || { echo "Missing stage after $1" >&2; exit 2; }; from=$(idx "$2") || { echo "Unknown stage: $2" >&2; exit 2; }; shift 2;;
    --to) [[ $# -ge 2 ]] || { echo "Missing stage after --to" >&2; exit 2; }; to=$(idx "$2") || { echo "Unknown stage: $2" >&2; exit 2; }; shift 2;;
    *) echo "Unknown option: $1" >&2; exit 2;;
  esac
done
(( from <= to )) || { echo "--from stage occurs after --to stage" >&2; exit 2; }
for ((i=from;i<=to;i++)); do run "${stages[$i]}"; done
