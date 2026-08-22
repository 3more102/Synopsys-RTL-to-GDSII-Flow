#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DEFAULT_GRAPH=ROOT/'config'/'stage_graph.json'
DEFAULT_POLICY=ROOT/'config'/'fingerprint_policy.json'

def load_json(p): return json.loads(Path(p).read_text())
def topo(stages):
    seen,temp,out=set(),set(),[]
    def visit(n):
        if n in temp: raise ValueError(f'cycle detected at {n}')
        if n in seen:return
        temp.add(n)
        for d in stages[n].get('depends_on',[]):
            if d not in stages: raise ValueError(f'{n}: unknown dependency {d}')
            visit(d)
        temp.remove(n);seen.add(n);out.append(n)
    for n in stages:visit(n)
    return out

def descendants(stages,seeds):
    rev={n:set() for n in stages}
    for n,cfg in stages.items():
        for d in cfg.get('depends_on',[]): rev[d].add(n)
    out=set(seeds); stack=list(seeds)
    while stack:
        for c in rev[stack.pop()]:
            if c not in out:out.add(c);stack.append(c)
    return out

def ancestors(stages,target):
    out=set()
    def walk(n):
        if n in out:return
        out.add(n)
        for d in stages[n].get('depends_on',[]):walk(d)
    walk(target);return out

def fp_state(root,stage,evidence,known):
    ev=root/evidence if evidence else None
    if not ev or not ev.exists(): return 'NOT_RUN','stage evidence is absent'
    if stage not in known:return 'NO_POLICY','stage evidence exists but no fingerprint policy is defined'
    cp=subprocess.run([sys.executable,str(root/'python'/'stage_fingerprint.py'),'check','--stage',stage,'--quiet'],cwd=root,text=True,capture_output=True)
    if cp.returncode==0:return 'FRESH','input fingerprint matches current inputs'
    if cp.returncode==3:return 'STALE','input fingerprint differs from current RTL/config/PDK/tool identity'
    if cp.returncode==4:return 'UNVERIFIABLE','checkpoint exists but saved fingerprint is missing'
    msg=(cp.stdout+' '+cp.stderr).strip().replace('\n',' ')
    return 'ERROR',f'fingerprint checker rc={cp.returncode}: {msg[:240]}'

def main():
    ap=argparse.ArgumentParser(description='Plan ASIC checkpoint rebuilds without invoking licensed EDA tools.')
    ap.add_argument('--root',default=str(ROOT));ap.add_argument('--graph',default=str(DEFAULT_GRAPH));ap.add_argument('--policy',default=str(DEFAULT_POLICY));ap.add_argument('--stage');ap.add_argument('--fail-on-stale',action='store_true');ap.add_argument('--json-out');ap.add_argument('--md-out')
    a=ap.parse_args();root=Path(a.root).resolve();graph=load_json(a.graph);policy=load_json(a.policy)
    if graph.get('schema_version')!=1:raise SystemExit('ERROR: unsupported stage graph schema')
    stages=graph['stages'];order=topo(stages);known=set(policy.get('stages',{}));target=graph.get('aliases',{}).get(a.stage,a.stage) if a.stage else None
    if target and target not in stages:raise SystemExit(f'ERROR: unknown stage {a.stage}')
    scope=ancestors(stages,target) if target else set(stages)
    states={};seeds=[]
    for s in order:
        state,detail=fp_state(root,s,stages[s].get('evidence',''),known);states[s]=(state,detail)
        if s in scope and state in {'STALE','UNVERIFIABLE','ERROR'}:seeds.append(s)
    rebuild=descendants(stages,seeds)&scope if seeds else set(); earliest=next((s for s in order if s in rebuild),None)
    rows=[{'stage':s,'state':states[s][0],'detail':states[s][1],'evidence':stages[s].get('evidence',''),'rebuild_required':s in rebuild} for s in order if s in scope]
    result={'schema_version':1,'target':target,'earliest_rebuild_stage':earliest,'rebuild_required':bool(rebuild),'stale_seeds':seeds,'stages':rows}
    jout=Path(a.json_out) if a.json_out else root/'reports'/'summary'/'rebuild_plan.json';mout=Path(a.md_out) if a.md_out else root/'reports'/'summary'/'rebuild_plan.md';jout.parent.mkdir(parents=True,exist_ok=True);mout.parent.mkdir(parents=True,exist_ok=True);jout.write_text(json.dumps(result,indent=2)+'\n')
    md=['# ASIC Rebuild Plan','',f"- Target: `{target or 'all'}`",f"- Earliest rebuild stage: `{earliest or 'none'}`",f"- Rebuild required: **{'YES' if rebuild else 'NO'}**",'', '| Stage | State | Rebuild | Detail |','|---|---|---:|---|']
    for r in rows:md.append(f"| {r['stage']} | {r['state']} | {'YES' if r['rebuild_required'] else 'no'} | {r['detail']} |")
    mout.write_text('\n'.join(md)+'\n');print(mout);print(f"REBUILD_FROM={earliest or 'NONE'}")
    return 3 if a.fail_on_stale and rebuild else 0
if __name__=='__main__':raise SystemExit(main())
