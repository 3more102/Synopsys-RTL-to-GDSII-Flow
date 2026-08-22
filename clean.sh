#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mode="${1:-clean}"
safe_rm_contents(){
  local p="$1"; p="$(realpath -m "$p")"
  [[ -n "$p" && "$p" == "$ROOT"/* && "$p" != "$ROOT/rtl" && "$p" != "$ROOT/constraints" && "$p" != "$ROOT/config" && "$p" != "$ROOT/scripts" ]] || { echo "Refusing unsafe deletion: $p" >&2; exit 2; }
  [[ -d "$p" ]] && find "$p" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
}
case "$mode" in
  clean) safe_rm_contents "$ROOT/work" ;;
  clean-results) for d in reports logs final_delivery; do safe_rm_contents "$ROOT/$d"; done ;;
  # Generated implementation artifacts/database are intentionally retained here so Make checkpoint stamps remain valid.
  distclean) for d in work reports results netlist spef sdf gds extracted final_delivery database checkpoints; do safe_rm_contents "$ROOT/$d"; done ;;
  *) echo "Usage: $0 {clean|clean-results|distclean}"; exit 2;;
esac
