#!/usr/bin/env bash
set -uo pipefail
if [[ $# -ne 4 ]]; then echo "Usage: $0 <stage-name> <tool-command> <tcl-script> <log-file>" >&2; exit 2; fi
stage="$1"; tool="$2"; script="$3"; log="$4"; ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; slug="$(printf '%s' "$stage" | tr -cs 'A-Za-z0-9_.-' '_')"
runtime_dir="$ROOT/reports/runtime"; status_dir="$ROOT/reports/status"; lock_root="$ROOT/work/locks"; lock_dir="$lock_root/$slug.lock"; mkdir -p "$(dirname "$log")" "$runtime_dir" "$status_dir" "$lock_root"
[[ -f "$script" ]] || { echo "ERROR: Tcl script not found: $script" >&2; exit 2; }; command -v "$tool" >/dev/null 2>&1 || { echo "ERROR: tool executable not found in PATH: $tool" >&2; exit 127; }
if ! mkdir "$lock_dir" 2>/dev/null; then echo "ERROR: stage '$stage' is already locked: $lock_dir" >&2; echo "If no flow is running, inspect/remove the stale lock manually." >&2; exit 73; fi
cleanup_lock(){ rmdir "$lock_dir" 2>/dev/null || true; }; trap cleanup_lock EXIT INT TERM HUP
json_escape(){ local s="$1"; s="${s//\\/\\\\}"; s="${s//\"/\\\"}"; s="${s//$'\n'/\\n}"; printf '%s' "$s"; }
start_epoch="$(date +%s)"; start_iso="$(date -Is)"; tool_path="$(command -v "$tool")"; git_commit="N/A"; git_dirty="N/A"
if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then git_commit="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo UNKNOWN)"; if [[ -n "$(git -C "$ROOT" status --porcelain 2>/dev/null)" ]]; then git_dirty=true; else git_dirty=false; fi; fi
extra_args=(); if [[ -n "${EDA_TOOL_ARGS:-}" ]]; then read -r -a extra_args <<< "$EDA_TOOL_ARGS"; fi
set +e
{ echo "================================================================"; echo "ASIC FLOW STAGE METADATA"; echo "stage=$stage"; echo "project=${PROJECT_NAME:-MIPS_16}"; echo "top=${TOP_MODULE:-mips_16}"; echo "flow_run_id=${FLOW_RUN_ID:-UNSET}"; echo "start=$start_iso"; echo "hostname=$(hostname)"; echo "user=$(id -un)"; echo "tool=$tool"; echo "tool_path=$tool_path"; echo "script=$(realpath -m "$script")"; echo "project_root=$ROOT"; echo "run_directory=$(pwd)"; echo "git_commit=$git_commit"; echo "git_dirty=$git_dirty"; echo "================================================================"; "$tool" "${extra_args[@]}" -f "$script"; } 2>&1 | tee "$log"
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
EOF_STATUS
echo "================================================================" | tee -a "$log"; echo "stage=$stage exit_code=$rc duration_seconds=$duration" | tee -a "$log"; echo "runtime_metadata=$meta" | tee -a "$log"; if [[ -n "$triage_md" ]]; then echo "failure_triage=$triage_md" | tee -a "$log"; fi; echo "================================================================" | tee -a "$log"
if [[ $rc -ne 0 ]]; then echo "ERROR: stage '$stage' failed with exit code $rc" >&2; fi
exit "$rc"
