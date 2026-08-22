#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,shutil,subprocess
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]; CONFIG=ROOT/"config"/"tool_capabilities.json"; PROBE_TCL=ROOT/"scripts"/"common"/"capability_probe.tcl"; OUT_DIR=ROOT/"reports"/"capabilities"

def summarize(results: dict[str,Any]) -> tuple[str,list[str],list[str]]:
    failures=[]; unknowns=[]
    for kind,data in results.items():
        status=data.get("status")
        if status == "UNAVAILABLE": unknowns.append(f"{kind}: tool unavailable"); continue
        if status != "AVAILABLE": failures.append(f"{kind}: capability probe failed ({status})"); continue
        for cmd,meta in data.get("commands",{}).items():
            if meta.get("required") and not meta.get("supported"): failures.append(f"{kind}: required command missing: {cmd}")
    return ("FAIL" if failures else "UNKNOWN" if unknowns else "PASS"),failures,unknowns

def main() -> int:
    ap=argparse.ArgumentParser(description="Probe installed Synopsys shells for release-specific command availability without loading a design."); ap.add_argument("--config",default=str(CONFIG)); ap.add_argument("--out-dir",default=str(OUT_DIR)); ap.add_argument("--require",action="store_true"); args=ap.parse_args()
    cfg=json.loads(Path(args.config).read_text()); out_dir=Path(args.out_dir); out_dir.mkdir(parents=True,exist_ok=True); results={}
    if cfg.get("schema_version") != 1: raise SystemExit("unsupported tool capability schema")
    for kind,spec in cfg["tools"].items():
        exe_name=os.environ.get(spec["env"],spec["default"]); exe=shutil.which(exe_name); out=out_dir/f"{kind}.json"
        if not exe:
            data={"schema_version":1,"tool_kind":kind,"tool":exe_name,"status":"UNAVAILABLE","commands":{c:{"supported":False,"required":c in spec.get("required",[])} for c in spec.get("required",[])+spec.get("optional",[])}}
            out.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n"); results[kind]=data; print(f"CAPABILITY {kind}: UNAVAILABLE ({exe_name})"); continue
        commands=spec.get("required",[])+spec.get("optional",[]); env=os.environ.copy(); env.update({"PROBE_TOOL_KIND":kind,"PROBE_OUTPUT":str(out.resolve()),"PROBE_COMMANDS":" ".join(commands),"PROBE_REQUIRED_COMMANDS":" ".join(spec.get("required",[]))}); log=out_dir/f"{kind}.log"
        with log.open("w") as fh: proc=subprocess.run([exe,"-f",str(PROBE_TCL)],env=env,stdout=fh,stderr=subprocess.STDOUT,text=True)
        if proc.returncode != 0 or not out.is_file(): data={"schema_version":1,"tool_kind":kind,"tool":exe,"status":"PROBE_FAILED","exit_code":proc.returncode,"commands":{}}; out.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
        else: data=json.loads(out.read_text()); data["tool"]=exe; out.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
        results[kind]=data; missing=[c for c,m in data.get("commands",{}).items() if m.get("required") and not m.get("supported")]; print(f"CAPABILITY {kind}: {data.get('status')} missing_required={len(missing)}")
    status,failures,unknowns=summarize(results); summary={"schema_version":1,"status":status,"failures":failures,"unknowns":unknowns,"tools":results}; (out_dir/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    md=["# Tool Capability Probe","",f"**Status:** {status}",""]
    for kind,data in results.items():
        md += [f"## {kind}",f"- Status: `{data.get('status')}`",f"- Tool: `{data.get('tool','')}`",f"- Version: `{data.get('tool_version','UNKNOWN')}`"]
        miss=[c for c,m in data.get("commands",{}).items() if m.get("required") and not m.get("supported")]; md += [f"- Missing required commands: {', '.join(miss) if miss else 'none'}",""]
    (out_dir/"summary.md").write_text("\n".join(md)+"\n")
    require=args.require or os.environ.get("REQUIRE_TOOL_CAPABILITIES","0") == "1"
    if require and status != "PASS":
        for problem in failures+unknowns: print(f"ERROR: {problem}")
        return 1
    return 0

if __name__ == "__main__": raise SystemExit(main())
