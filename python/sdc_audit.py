#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "sdc_audit_policy.json"
DEFAULT_CONSTRAINTS = ROOT / "constraints"
DEFAULT_JSON = ROOT / "reports" / "audit" / "sdc_audit.json"
DEFAULT_MD = ROOT / "reports" / "audit" / "sdc_audit.md"

@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    file: str
    line: int
    message: str
    command: str


def strip_comment(line: str) -> str:
    out=[]; quote=False; brace=0; i=0
    while i < len(line):
        ch=line[i]
        if ch == '"' and (i == 0 or line[i-1] != "\\") and brace == 0: quote = not quote
        elif ch == "{" and not quote: brace += 1
        elif ch == "}" and not quote and brace: brace -= 1
        elif ch == "#" and not quote and brace == 0 and (i == 0 or line[i-1].isspace()): break
        out.append(ch); i += 1
    return "".join(out).strip()


def logical_commands(text: str) -> list[tuple[int,str]]:
    commands=[]; buf=""; start=1
    for lineno,raw in enumerate(text.splitlines(),1):
        line=strip_comment(raw)
        if not line: continue
        if not buf: start=lineno
        if line.endswith("\\"):
            buf += line[:-1] + " "; continue
        buf += line
        commands.append((start,re.sub(r"\s+"," ",buf).strip())); buf=""
    if buf: commands.append((start,re.sub(r"\s+"," ",buf).strip()))
    return commands


def command_name(cmd: str) -> str:
    m=re.match(r"^([A-Za-z_][\w:]*)\b",cmd)
    return m.group(1) if m else ""


def multicycle_signature(cmd: str) -> tuple[str,int|None,str]:
    mode="setup" if re.search(r"\s-setup\b",cmd) else "hold" if re.search(r"\s-hold\b",cmd) else "setup"
    m=re.match(r"^set_multicycle_path\s+(\d+)\b",cmd); cycles=int(m.group(1)) if m else None
    sig=re.sub(r"^set_multicycle_path\s+\d+\b","set_multicycle_path",cmd)
    sig=re.sub(r"\s-(?:setup|hold)\b","",sig); sig=re.sub(r"\s+"," ",sig).strip()
    return mode,cycles,sig


def audit(constraints: Path, policy: dict[str,Any]) -> dict[str,Any]:
    findings=[]; files=sorted(constraints.glob("*.sdc")) if constraints.is_dir() else [constraints]
    clock_count=0; mc_setup={}; mc_hold={}; risky=set(policy.get("risky_commands",[])); broad_getters=policy.get("broad_collection_commands",[])
    for path in files:
        rel=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        for lineno,cmd in logical_commands(path.read_text(errors="ignore")):
            name=command_name(cmd)
            if name == "create_clock": clock_count += 1
            if name == "set_false_path" and not re.search(r"\s-(?:from|to|through)\b",cmd):
                findings.append(Finding("ERROR","GLOBAL_FALSE_PATH",rel,lineno,"set_false_path has no -from/-to/-through selector and may disable all timing paths.",cmd))
            if name == "set_clock_groups" and "-asynchronous" in cmd and "-group" not in cmd:
                findings.append(Finding("ERROR","ASYNC_CLOCK_GROUP_WITHOUT_GROUPS",rel,lineno,"Asynchronous clock grouping has no explicit -group clauses.",cmd))
            if name == "set_disable_timing": findings.append(Finding("WARNING","DISABLE_TIMING_PRESENT",rel,lineno,"Disabled timing arcs require explicit design justification and signoff review.",cmd))
            if name == "set_case_analysis": findings.append(Finding("INFO","CASE_ANALYSIS_PRESENT",rel,lineno,"Case analysis changes reachable timing paths; audit the intended mode/scenario.",cmd))
            if name in risky:
                for getter in broad_getters:
                    if re.search(rf"\[{re.escape(getter)}(?:\s+-\w+)*\s+['\"]?\*['\"]?\s*\]",cmd):
                        findings.append(Finding("ERROR","BROAD_WILDCARD_EXCEPTION",rel,lineno,f"Risky timing command uses broad [{getter} *] selection.",cmd))
                if name == "set_false_path" and re.search(r"\[all_registers\]",cmd): findings.append(Finding("ERROR","ALL_REGISTERS_FALSE_PATH",rel,lineno,"False-pathing all registers can hide most synchronous timing.",cmd))
            if name == "set_multicycle_path":
                mode,cycles,sig=multicycle_signature(cmd)
                if cycles is None: findings.append(Finding("ERROR","MULTICYCLE_COUNT_UNPARSED",rel,lineno,"Could not parse multicycle count.",cmd))
                elif mode == "setup": mc_setup[sig]=(cycles,rel,lineno)
                else: mc_hold[sig]=(cycles,rel,lineno)
    if policy.get("require_primary_clock",True) and clock_count == 0:
        findings.append(Finding("ERROR","NO_CREATE_CLOCK",str(constraints),0,"No active create_clock command was found in the audited SDC set.",""))
    for sig,(setup_n,rel,line) in mc_setup.items():
        if setup_n <= 1: continue
        hold=mc_hold.get(sig); expected=setup_n-1
        if hold is None: findings.append(Finding("WARNING","MULTICYCLE_HOLD_PAIR_MISSING",rel,line,f"Setup multicycle {setup_n} has no matching hold multicycle; common methodology uses hold {expected}.",sig))
        elif hold[0] != expected: findings.append(Finding("WARNING","MULTICYCLE_HOLD_PAIR_UNUSUAL",hold[1],hold[2],f"Setup multicycle {setup_n} is paired with hold {hold[0]}; expected {expected} in the common convention.",sig))
    ignore=set(policy.get("ignore_codes",[])); findings=[f for f in findings if f.code not in ignore]
    counts={sev:sum(1 for f in findings if f.severity==sev) for sev in ("ERROR","WARNING","INFO")}
    fail_sev=set(policy.get("fail_severities",["ERROR"])); status="FAIL" if any(f.severity in fail_sev for f in findings) else "PASS"
    return {"schema_version":1,"status":status,"constraints":str(constraints),"files_scanned":[str(p) for p in files],"active_create_clock_count":clock_count,"counts":counts,"findings":[asdict(f) for f in findings],"limitations":"Static heuristic audit only; always complement with tool-native check_timing/report_exceptions/coverage review."}


def write_reports(result: dict[str,Any], json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True,exist_ok=True); md_path.parent.mkdir(parents=True,exist_ok=True)
    json_path.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    lines=["# SDC Safety Audit","",f"**Status:** {result['status']}",f"**Active create_clock commands:** {result['active_create_clock_count']}",f"**Findings:** {result['counts']}","","This is a static heuristic audit. It does not replace Synopsys `check_timing`, timing coverage, or exception reports.",""]
    if result["findings"]:
        lines += ["| Severity | Code | File | Line | Message |","|---|---|---|---:|---|"]
        for f in result["findings"]:
            msg=f["message"].replace("|","\\|"); lines.append(f"| {f['severity']} | {f['code']} | `{f['file']}` | {f['line']} | {msg} |")
    else: lines.append("No static SDC policy findings.")
    md_path.write_text("\n".join(lines)+"\n")


def main() -> int:
    ap=argparse.ArgumentParser(description="Static heuristic SDC safety audit.")
    ap.add_argument("--constraints",default=str(DEFAULT_CONSTRAINTS)); ap.add_argument("--policy",default=str(DEFAULT_POLICY)); ap.add_argument("--json",default=str(DEFAULT_JSON)); ap.add_argument("--markdown",default=str(DEFAULT_MD)); ap.add_argument("--check",action="store_true",help="Exit nonzero when policy fail severities are present.")
    args=ap.parse_args(); policy=json.loads(Path(args.policy).read_text())
    if policy.get("schema_version") != 1: raise SystemExit("unsupported SDC audit policy schema")
    result=audit(Path(args.constraints),policy); write_reports(result,Path(args.json),Path(args.markdown))
    print(f"SDC_AUDIT status={result['status']} errors={result['counts']['ERROR']} warnings={result['counts']['WARNING']} report={args.markdown}")
    return 1 if args.check and result["status"] == "FAIL" else 0

if __name__ == "__main__": raise SystemExit(main())
