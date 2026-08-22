#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
[[ $# -eq 1 ]] || { echo "Usage: $0 <prepared-tag>" >&2; exit 2; }
tag="$1"; cfg="$ROOT/runs/dse/$tag/point.env"
[[ -f "$cfg" ]] || { echo "ERROR: DSE point not prepared: $cfg" >&2; exit 2; }
run="$ROOT/runs/dse/$tag"
ws="$run/workspace"
[[ ! -e "$ws" ]] || { echo "ERROR: workspace already exists: $ws (remove it deliberately before rerunning)" >&2; exit 2; }
mkdir -p "$ws"
for f in Makefile README.md setup.sh run_flow.sh resume.sh clean.sh .gitignore .env.example; do [[ -f "$ROOT/$f" ]] && cp -a "$ROOT/$f" "$ws/"; done
for d in config constraints power_intent scripts python rtl docs lib tech; do [[ -e "$ROOT/$d" ]] && cp -a "$ROOT/$d" "$ws/"; done
mkdir -p "$ws"/{work,logs,reports,results,checkpoints,database,extracted,gds,netlist,sdf,spef,saif,screenshots,final_delivery,runs}
set -a; source "$cfg"; set +a
export ASIC_PROJECT_ROOT="$ws"
( cd "$ws" && make all ) 2>&1 | tee "$run/dse_run.log"
echo "DSE point complete: $run"
