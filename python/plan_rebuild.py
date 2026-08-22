#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH = ROOT / "config" / "stage_graph.json"
DEFAULT_POLICY = ROOT / "config" / "fingerprint_policy.json"


def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def topo(stages: dict) -> list[str]:
    seen: set[str] = set()
    active: set[str] = set()
    out: list[str] = []

    def visit(stage: str) -> None:
        if stage in active:
            raise ValueError(f"cycle detected at {stage}")
        if stage in seen:
            return
        active.add(stage)
        for dep in stages[stage].get("depends_on", []):
            if dep not in stages:
                raise ValueError(f"{stage}: unknown dependency {dep}")
            visit(dep)
        active.remove(stage)
        seen.add(stage)
        out.append(stage)

    for stage in stages:
        visit(stage)
    return out


def descendants(stages: dict, seeds: list[str] | set[str]) -> set[str]:
    reverse = {stage: set() for stage in stages}
    for stage, cfg in stages.items():
        for dep in cfg.get("depends_on", []):
            reverse[dep].add(stage)
    out = set(seeds)
    stack = list(seeds)
    while stack:
        stage = stack.pop()
        for child in reverse[stage]:
            if child not in out:
                out.add(child)
                stack.append(child)
    return out


def ancestors(stages: dict, target: str) -> set[str]:
    out: set[str] = set()

    def walk(stage: str) -> None:
        if stage in out:
            return
        out.add(stage)
        for dep in stages[stage].get("depends_on", []):
            walk(dep)

    walk(target)
    return out


def fingerprint_state(root: Path, stage: str, cfg: dict, known: set[str]) -> tuple[str, str]:
    evidence = cfg.get("evidence", "")
    evidence_path = root / evidence if evidence else None
    if not evidence_path or not evidence_path.exists():
        return "NOT_RUN", "stage evidence is absent"

    fp_stage = cfg.get("fingerprint", stage)
    if fp_stage not in known:
        return "NO_POLICY", f"stage evidence exists but fingerprint stage '{fp_stage}' is undefined"

    cp = subprocess.run(
        [sys.executable, str(root / "python" / "stage_fingerprint.py"), "check", "--stage", fp_stage, "--quiet"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if cp.returncode == 0:
        return "FRESH", "input fingerprint matches current inputs"
    if cp.returncode == 3:
        return "STALE", "input fingerprint differs from current RTL/config/PDK/tool identity"
    if cp.returncode == 4:
        return "UNVERIFIABLE", "checkpoint exists but saved fingerprint is missing"
    message = (cp.stdout + " " + cp.stderr).strip().replace("\n", " ")
    return "ERROR", f"fingerprint checker rc={cp.returncode}: {message[:240]}"


def build_plan(root: Path, graph: dict, policy: dict, target: str | None, include_not_run: bool) -> dict:
    if graph.get("schema_version") != 2:
        raise ValueError(f"unsupported stage graph schema_version={graph.get('schema_version')!r}; expected 2")

    stages = graph["stages"]
    order = topo(stages)
    known = set(policy.get("stages", {}))
    canonical_target = graph.get("aliases", {}).get(target, target) if target else None
    if canonical_target and canonical_target not in stages:
        raise ValueError(f"unknown stage {target}")

    scope = ancestors(stages, canonical_target) if canonical_target else set(stages)
    states: dict[str, tuple[str, str]] = {}
    seeds: list[str] = []
    for stage in order:
        state, detail = fingerprint_state(root, stage, stages[stage], known)
        states[stage] = (state, detail)
        if stage not in scope:
            continue
        bad = state in {"STALE", "UNVERIFIABLE", "ERROR"}
        missing = include_not_run and state == "NOT_RUN"
        if bad or missing:
            seeds.append(stage)

    rebuild = descendants(stages, seeds) & scope if seeds else set()
    earliest = next((stage for stage in order if stage in rebuild), None)
    rows = []
    execution_targets = []
    for stage in order:
        if stage not in scope:
            continue
        cfg = stages[stage]
        target_name = cfg.get("target", "")
        rebuild_required = stage in rebuild
        if rebuild_required and target_name:
            execution_targets.append(target_name)
        rows.append(
            {
                "stage": stage,
                "make_target": target_name,
                "fingerprint_stage": cfg.get("fingerprint", stage),
                "state": states[stage][0],
                "detail": states[stage][1],
                "evidence": cfg.get("evidence", ""),
                "rebuild_required": rebuild_required,
            }
        )

    return {
        "schema_version": 2,
        "target": canonical_target,
        "include_not_run": include_not_run,
        "earliest_rebuild_stage": earliest,
        "earliest_make_target": stages[earliest].get("target", "") if earliest else None,
        "rebuild_required": bool(rebuild),
        "rebuild_seeds": seeds,
        "execution_targets": execution_targets,
        "stages": rows,
    }


def write_outputs(root: Path, result: dict, json_out: str | None, md_out: str | None) -> tuple[Path, Path]:
    jout = Path(json_out) if json_out else root / "reports" / "summary" / "rebuild_plan.json"
    mout = Path(md_out) if md_out else root / "reports" / "summary" / "rebuild_plan.md"
    if not jout.is_absolute():
        jout = root / jout
    if not mout.is_absolute():
        mout = root / mout
    jout.parent.mkdir(parents=True, exist_ok=True)
    mout.parent.mkdir(parents=True, exist_ok=True)
    jout.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    md = [
        "# ASIC Rebuild Plan",
        "",
        f"- Target: `{result['target'] or 'all'}`",
        f"- Include never-run stages: **{'YES' if result['include_not_run'] else 'NO'}**",
        f"- Earliest rebuild stage: `{result['earliest_rebuild_stage'] or 'none'}`",
        f"- Earliest Make target: `{result['earliest_make_target'] or 'none'}`",
        f"- Rebuild required: **{'YES' if result['rebuild_required'] else 'NO'}**",
        "",
        "| Stage | Make target | State | Rebuild | Detail |",
        "|---|---|---|---:|---|",
    ]
    for row in result["stages"]:
        md.append(
            f"| {row['stage']} | {row['make_target']} | {row['state']} | "
            f"{'YES' if row['rebuild_required'] else 'no'} | {row['detail']} |"
        )
    if result["execution_targets"]:
        md.extend(["", "## Execution targets", "", "```text", *result["execution_targets"], "```"])
    mout.write_text("\n".join(md) + "\n", encoding="utf-8")
    return jout, mout


def main() -> int:
    ap = argparse.ArgumentParser(description="Plan ASIC checkpoint rebuilds without invoking licensed EDA tools.")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--graph", default=str(DEFAULT_GRAPH))
    ap.add_argument("--policy", default=str(DEFAULT_POLICY))
    ap.add_argument("--stage", help="Limit plan to the dependency cone required to build this stage/target.")
    ap.add_argument("--include-not-run", action="store_true", help="Treat never-run required stages as rebuild seeds.")
    ap.add_argument("--fail-on-stale", action="store_true", help="Exit nonzero when rebuild is required.")
    ap.add_argument("--json-out")
    ap.add_argument("--md-out")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    try:
        graph = load_json(Path(args.graph).resolve())
        policy = load_json(Path(args.policy).resolve())
        result = build_plan(root, graph, policy, args.stage, args.include_not_run)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    _, md_path = write_outputs(root, result, args.json_out, args.md_out)
    print(md_path)
    print(f"REBUILD_FROM={result['earliest_rebuild_stage'] or 'NONE'}")
    print(f"MAKE_FROM={result['earliest_make_target'] or 'NONE'}")
    if result["execution_targets"]:
        print("EXECUTION_TARGETS=" + " ".join(result["execution_targets"]))
    else:
        print("EXECUTION_TARGETS=NONE")
    return 3 if args.fail_on_stale and result["rebuild_required"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
