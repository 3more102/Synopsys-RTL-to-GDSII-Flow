#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
helper="python/stage_locks.py"
usage(){ cat <<'EOF'
Usage:
  ./locks.sh list [--json]
  ./locks.sh check --stage STAGE [--json]
  ./locks.sh recover --stage STAGE [--force-unknown]

Recovery never deletes a lock. It archives it under work/stale_locks/.
Automatic/safe recovery accepts only proven STALE locks from a prior boot.
UNKNOWN same-boot locks require explicit --force-unknown after engineer review.
ACTIVE and FOREIGN_HOST locks are always protected.
EOF
}
[[ $# -gt 0 ]] || { usage; exit 2; }
cmd="$1"; shift
case "$cmd" in
  list)
    exec python3 "$helper" list "$@"
    ;;
  check|recover)
    stage=""; json=0; force_unknown=0
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --stage) [[ $# -ge 2 ]] || { echo "ERROR: --stage requires a value" >&2; exit 2; }; stage="$2"; shift 2;;
        --json) json=1; shift;;
        --force-unknown) force_unknown=1; shift;;
        --help|-h) usage; exit 0;;
        *) echo "ERROR: unknown option: $1" >&2; exit 2;;
      esac
    done
    [[ -n "$stage" ]] || { echo "ERROR: --stage is required" >&2; exit 2; }
    slug="$(printf '%s' "$stage" | tr -cs 'A-Za-z0-9_.-' '_')"
    lock="work/locks/${slug}.lock"
    if [[ "$cmd" == "check" ]]; then
      args=(check --lock "$lock")
      (( json )) && args+=(--json)
      exec python3 "$helper" "${args[@]}"
    fi
    args=(recover --lock "$lock")
    (( force_unknown )) && args+=(--force-unknown)
    exec python3 "$helper" "${args[@]}"
    ;;
  --help|-h) usage;;
  *) echo "ERROR: unknown command: $cmd" >&2; usage >&2; exit 2;;
esac
