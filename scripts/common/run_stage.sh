#!/usr/bin/env bash
set -uo pipefail
if [[ $# -ne 4 ]]; then echo "Usage: $0 <stage-name> <tool-command> <tcl-script> <log-file>" >&2; exit 2; fi
stage="$1"; tool="$2"; script="$3"; log="$4"; ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; slug="$(printf '%s' "$stage" | tr -cs 'A-Za-z0-9_.-' '_')"
runtime_dir="$ROOT/reports/runtime"; status_dir="$ROOT/reports/status"; lock_root="$ROOT/work/locks"; lock_dir="$lock_root/$slug.lock"; lock_helper="$ROOT/python/stage_locks.py"; mkdir -p "$(dirname "$log")" "$runtime_dir" "$status_dir" "$lock_root"
[[ -f "$script" ]] || { echo "ERROR: Tcl script not found: $script" >&2; exit 2; }; command -v "$tool" >/dev/null 2>&1 || { echo "ERROR: tool executable not found in PATH: $tool" >&2; exit 127; }

acquire_stage_lock(){
  if mkdir "$lock_dir" 2>/dev/null; then return 0; fi
  echo "WARNING: stage lock already exists: $lock_dir" >&2
  if [[ -f "$lock_helper" ]]; then
    set +e
    lock_info="$(python3 "$lock_helper" check --lock "$lock_dir" 2>&1)"; lock_check_rc=$?
    set -e
    printf '%s\n' "$lock_info" >&2
    lock_state="$(printf '%s\n' "$lock_info" | sed -n 's/^LOCK_STATE=//p' | tail -1)"
    if [[ $lock_check_rc -eq 0 && "$lock_state" == "STALE" && "${FLOW_RECOVER_STALE_LOCKS:-0}" == "1" ]]; then
      echo "Recovering proven-stale local lock because FLOW_RECOVER_STALE_LOCKS=1." >&2
      if python3 "$lock_helper" recover --lock "$lock_dir" >&2 && mkdir "$lock_dir" 2>/dev/null; then
        return 0
      fi
      echo "ERROR: stale lock recovery/reacquisition failed: $lock_dir" >&2
      return 73
    fi
    if [[ "$lock_state" == "STALE" ]]; then
      echo "The lock is proven stale. Review it, then use './locks.sh recover --stage $slug' or set FLOW_RECOVER_STALE_LOCKS=1." >&2
    elif [[ "$lock_state" == "FOREIGN_HOST" ]]; then
      echo "Refusing automatic recovery because the lock belongs to another host." >&2
    elif [[ "$lock_state" == "ACTIVE" ]]; then
      echo "Refusing recovery because the recorded owner process is active." >&2
    else
      echo "Lock ownership is not provable; inspect manually. Unknown locks are never auto-deleted." >&2
    fi
  else
    echo "Lock inspection helper is unavailable; no automatic recovery is attempted." >&2
  fi
  return 73
}

if ! acquire_stage_lock; then exit 73; fi
cleanup_lock(){
  [[ -f "$lock_dir/owner.json" ]] && unlink "$lock_dir/owner.json" 2>/dev/null || true
  rmdir "$lock_dir" 2>/dev/null || true
}
trap cleanup_lock EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

if [[ -f "$lock_helper" ]]; then
  if ! python3 "$lock_helper" record --lock "$lock_dir" --stage "$stage" --tool "$tool" --script "$script" --flow-run-id "${FLOW_RUN_ID:-UNSET}" --pid "$$" --ppid "$PPID" >/dev/null; then
    echo "ERROR: failed to record stage-lock ownership metadata; refusing to run an unowned lock." >&2
    exit 74
  fi
fi

json_escape(){ local s="$1"; s="${s//\\/\\\\}"; s="${s//\"/\\\"}"; s="${s//$'\n'/\\n}"; printf '%s' "$s"; }
start_epoch="$(date +%s)"; start_iso="$(date -Is)"; tool_path="$(command -v "$tool")"; git_commit="N/A"; git_dirty="N/A"
if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then git_commit="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo UNKNOWN)"; if [[ -n "$(git -C "$ROOT" status --porcelain 2>/dev/null)" ]]; then git_dirty=true; else git_dirty=false; fi; fi
extra_args=(); if [[ -n "${EDA_TOOL_ARGS:-}" ]]; then read -r -a extra_args <<< "$EDA_TOOL_ARGS"; fi
set +e
{ echo "================================================================"; echo "ASIC FLOW STAGE METADATA"; echo "stage=$stage"; echo "project=${PROJECT_NAME:-MIPS_16}"; echo "top=${TOP_MODULE:-mips_16}"; echo "flow_run_id=${FLOW_RUN_ID:-UNSET}"; echo "start=$start_iso"; echo "hostname=$(hostname)"; echo "user=$(id -un)"; echo "tool=$tool"; echo "tool_path=$tool_path"; echo "script=$(realpath -m "$script")"; echo "project_root=$ROOT"; echo "run_directory=$(pwd)"; echo "git_commit=$git_commit"; echo "git_dirty=$git_dirty"; echo "stage_lock=$lock_dir"; echo "stage_lock_owner=$lock_dir/owner.json"; echo "================================================================"; "$tool" "${extra_args[@]}" -f "$script"; } 2>&1 | tee "$log"
rc=${PIPESTATUS[0]}; set -e
fingerprint_digest=""; fingerprint_file=""
if [[ $rc -eq 0 && -f "$ROOT/python/stage_fingerprint.py" && -f "$ROOT/config/fingerprint_policy.json" ]]; then
  fp_log="$(python3 "$ROOT/python/stage_fingerprint.py" capture --stage "$stage" --if-known 2>&1)"; fp_rc=$?; printf '%s\n' "$fp_log" | tee -a "$log"
  if [[ $fp_rc -eq 0 ]]; then fp_stage="$(printf '%s\n' "$fp_log" | sed -n 's/^CAPTURED stage=\([^ ]*\).*/\1/p' | tail -1)"; fingerprint_digest="$(printf '%s\n' "$fp_log" | sed -n 's/^CAPTURED .* digest=\([^ ]*\).*/\1/p' | tail -1)"; if [[ -n "$fp_stage" ]]; then fingerprint_file="$ROOT/checkpoints/fingerprints/${fp_stage}.json"; fi
  elif [[ "${FINGERPRINT_REQUIRED:-0}" == "1" ]]; then echo "ERROR: fingerprint capture failed and FINGERPRINT_REQUIRED=1" | tee -a "$log" >&2; rc=74
  else echo "WARNING: fingerprint capture failed; stage result retained because FINGERPRINT_REQUIRED!=1" | tee -a "$log" >&2; fi
fi

# Triage only failed executions. This is deliberately heuristic: the generated
# report points engineers toward likely investigation categories but never marks
# a root cause as proven and never changes the tool exit code.
triage_json=""; triage_md=""; triage_primary=""; triage_category=""; triage_status="NOT_RUN"
if [[ $rc -ne 0 && -f "$ROOT/python/triage_failure.py" && -f "$ROOT/config/failure_signatures.json" ]]; then
  set +e
  triage_out="$(python3 "$ROOT/python/triage_failure.py" --log "$log" --stage "$stage" --tool "$tool" --exit-code "$rc" 2>&1)"; triage_rc=$?
  set -e
  printf '%s\n' "$triage_out" | tee -a "$log"
  if [[ $triage_rc -eq 0 ]]; then
    triage_status="$(printf '%s\n' "$triage_out" | sed -n 's/^TRIAGE_STATUS=//p' | tail -1)"
    triage_primary="$(printf '%s\n' "$triage_out" | sed -n 's/^TRIAGE_PRIMARY=//p' | tail -1)"
    triage_category="$(printf '%s\n' "$triage_out" | sed -n 's/^TRIAGE_CATEGORY=//p' | tail -1)"
    triage_json="$(printf '%s\n' "$triage_out" | sed -n 's/^TRIAGE_JSON=//p' | tail -1)"
    triage_md="$(printf '%s\n' "$triage_out" | sed -n 's/^TRIAGE_MARKDOWN=//p' | tail -1)"
  else
    triage_status="ERROR"
    echo "WARNING: automatic failure triage failed with rc=$triage_rc; original stage rc=$rc is preserved." | tee -a "$log" >&2
  fi
fi

end_epoch="$(date +%s)"; end_iso="$(date -Is)"; duration="$((end_epoch-start_epoch))"; stamp="$(date +%Y%m%d_%H%M%S)"; meta="$runtime_dir/${slug}_${stamp}.json"; latest="$runtime_dir/${slug}.latest.json"; runner_status="$status_dir/${slug}_runner.status"
cat > "$meta" <<EOF_META
{
  "stage": "$(json_escape "$stage")",
  "project": "$(json_escape "${PROJECT_NAME:-MIPS_16}")",
  "top": "$(json_escape "${TOP_MODULE:-mips_16}")",
  "flow_run_id": "$(json_escape "${FLOW_RUN_ID:-UNSET}")",
  "tool": "$(json_escape "$tool")",
  "tool_path": "$(json_escape "$tool_path")",
  "script": "$(json_escape "$(realpath -m "$script")")",
  "log": "$(json_escape "$(realpath -m "$log")")",
  "start": "$(json_escape "$start_iso")",
  "end": "$(json_escape "$end_iso")",
  "duration_seconds": $duration,
  "exit_code": $rc,
  "git_commit": "$(json_escape "$git_commit")",
  "git_dirty": "$(json_escape "$git_dirty")",
  "input_fingerprint": "$(json_escape "$fingerprint_file")",
  "input_digest": "$(json_escape "$fingerprint_digest")",
  "triage_status": "$(json_escape "$triage_status")",
  "triage_primary": "$(json_escape "$triage_primary")",
  "triage_category": "$(json_escape "$triage_category")",
  "triage_json": "$(json_escape "$triage_json")",
  "triage_markdown": "$(json_escape "$triage_md")"
}
EOF_META
cp -f "$meta" "$latest"

# Artifact provenance runs only after runtime metadata exists, so the artifact
# record can point back to the exact tool/run evidence that generated it. This
# capture is advisory in the stage runner; release verification can invoke the
# same builder with --strict-required as an explicit artifact gate.
artifact_provenance_status="NOT_RUN"; artifact_provenance_file=""; artifact_provenance_missing=""
if [[ $rc -eq 0 && -f "$ROOT/python/build_artifact_provenance.py" && -f "$ROOT/config/artifact_provenance.json" ]]; then
  set +e
  artifact_out="$(python3 "$ROOT/python/build_artifact_provenance.py" --stage "$stage" 2>&1)"; artifact_rc=$?
  set -e
  printf '%s\n' "$artifact_out" | tee -a "$log"
  if [[ $artifact_rc -eq 0 ]]; then
    artifact_provenance_status="$(printf '%s\n' "$artifact_out" | sed -n 's/^ARTIFACT_PROVENANCE_STATUS=//p' | tail -1)"
    artifact_provenance_file="$(printf '%s\n' "$artifact_out" | sed -n 's/^ARTIFACT_PROVENANCE=//p' | tail -1)"
    artifact_provenance_missing="$(printf '%s\n' "$artifact_out" | sed -n 's/^ARTIFACT_PROVENANCE_MISSING_REQUIRED=//p' | tail -1)"
    [[ -n "$artifact_provenance_status" ]] || artifact_provenance_status="UNKNOWN"
  else
    artifact_provenance_status="ERROR"
    echo "WARNING: artifact lineage capture failed with rc=$artifact_rc; tool stage result remains unchanged." | tee -a "$log" >&2
  fi
fi

if [[ $rc -eq 0 ]]; then
  runner_state=PASS; detail="Tool process completed with exit code 0; engineering quality remains report/status driven."
else
  runner_state=FAIL; detail="Tool process exited with code $rc. Inspect log=$log"
  if [[ -n "$triage_primary" && "$triage_primary" != "NONE" ]]; then detail="$detail; heuristic_triage=$triage_primary category=$triage_category report=$triage_md"; fi
fi
cat > "$runner_status" <<EOF_STATUS
stage=${slug}_runner
status=$runner_state
detail=$detail
time=$end_iso
runtime_seconds=$duration
metadata=$meta
triage_status=$triage_status
triage_primary=$triage_primary
triage_report=$triage_md
artifact_provenance_status=$artifact_provenance_status
artifact_provenance=$artifact_provenance_file
artifact_provenance_missing_required=$artifact_provenance_missing
EOF_STATUS
echo "================================================================" | tee -a "$log"; echo "stage=$stage exit_code=$rc duration_seconds=$duration" | tee -a "$log"; echo "runtime_metadata=$meta" | tee -a "$log"; if [[ -n "$triage_md" ]]; then echo "failure_triage=$triage_md" | tee -a "$log"; fi; if [[ -n "$artifact_provenance_file" ]]; then echo "artifact_provenance=$artifact_provenance_file status=$artifact_provenance_status missing_required=${artifact_provenance_missing:-0}" | tee -a "$log"; fi; echo "================================================================" | tee -a "$log"
if [[ $rc -ne 0 ]]; then echo "ERROR: stage '$stage' failed with exit code $rc" >&2; fi
exit "$rc"
