#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def topo(stages: dict) -> list[str]:
    seen: set[str] = set()
    active: set[str] = set()
    order: list[str] = []

    def visit(stage: str) -> None:
        if stage in active:
            raise ValueError(f"cycle detected at stage '{stage}'")
        if stage in seen:
            return
        active.add(stage)
        for dep in stages[stage].get("depends_on", []):
            if dep not in stages:
                raise ValueError(f"stage '{stage}' references unknown dependency '{dep}'")
            visit(dep)
        active.remove(stage)
        seen.add(stage)
        order.append(stage)

    for stage in stages:
        visit(stage)
    return order


def make_targets(makefile: Path) -> set[str]:
    targets: set[str] = set()
    pattern = re.compile(r"^([A-Za-z0-9_.-]+)\s*:(?![=])")
    for line in makefile.read_text(encoding="utf-8").splitlines():
        m = pattern.match(line)
        if m:
            targets.add(m.group(1))
    return targets


def validate(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    graph_path = root / "config" / "stage_graph.json"
    fp_path = root / "config" / "fingerprint_policy.json"
    makefile = root / "Makefile"

    for path in (graph_path, fp_path, makefile):
        if not path.is_file():
            errors.append(f"required flow-model file missing: {path.relative_to(root)}")
    if errors:
        return errors, warnings

    graph = load_json(graph_path)
    fp = load_json(fp_path)
    if graph.get("schema_version") != 2:
        errors.append(f"stage_graph.json schema_version must be 2, got {graph.get('schema_version')!r}")
    if fp.get("schema_version") != 1:
        errors.append(f"fingerprint_policy.json schema_version must be 1, got {fp.get('schema_version')!r}")

    stages = graph.get("stages", {})
    if not isinstance(stages, dict) or not stages:
        errors.append("stage_graph.json must define a non-empty stages object")
        return errors, warnings

    try:
        order = topo(stages)
    except ValueError as exc:
        errors.append(str(exc))
        order = list(stages)

    targets = make_targets(makefile)
    fp_stages = set(fp.get("stages", {}))
    fp_aliases = fp.get("aliases", {})
    graph_aliases = graph.get("aliases", {})

    seen_targets: dict[str, str] = {}
    seen_evidence: dict[str, str] = {}
    for stage in order:
        cfg = stages[stage]
        target = cfg.get("target", "")
        evidence = cfg.get("evidence", "")
        fingerprint = cfg.get("fingerprint", stage)

        if not target:
            errors.append(f"stage '{stage}' has no Make target")
        elif target not in targets:
            errors.append(f"stage '{stage}' maps to missing Make target '{target}'")
        elif target in seen_targets and seen_targets[target] != stage:
            errors.append(f"Make target '{target}' is shared by stages '{seen_targets[target]}' and '{stage}'")
        else:
            seen_targets[target] = stage

        if not evidence:
            errors.append(f"stage '{stage}' has no evidence path")
        elif Path(evidence).is_absolute():
            errors.append(f"stage '{stage}' evidence must be repository-relative: {evidence}")
        elif evidence in seen_evidence and seen_evidence[evidence] != stage:
            warnings.append(f"evidence path '{evidence}' is shared by '{seen_evidence[evidence]}' and '{stage}'")
        else:
            seen_evidence[evidence] = stage

        if fingerprint not in fp_stages:
            errors.append(f"stage '{stage}' maps to unknown fingerprint stage '{fingerprint}'")

        resolved = fp_aliases.get(target, target)
        if resolved != fingerprint:
            errors.append(
                f"Make target '{target}' resolves via fingerprint aliases to '{resolved}', "
                f"but graph stage '{stage}' expects '{fingerprint}'"
            )

    for alias, canonical in graph_aliases.items():
        if canonical not in stages:
            errors.append(f"stage_graph alias '{alias}' resolves to unknown stage '{canonical}'")

    graph_targets = {cfg.get("target") for cfg in stages.values() if cfg.get("target")}
    for alias, canonical in fp_aliases.items():
        if alias in graph_targets and canonical not in fp_stages:
            errors.append(f"fingerprint alias '{alias}' resolves to undefined fingerprint stage '{canonical}'")

    expected_core = {"synthesis", "floorplan", "placement", "cts", "route", "signoff", "gds"}
    missing_core = expected_core - set(stages)
    if missing_core:
        warnings.append("stage graph is missing common core stages: " + ", ".join(sorted(missing_core)))

    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate consistency of ASIC stage DAG, fingerprints, and Make targets.")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--json-out")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    errors, warnings = validate(root)
    result = {
        "schema_version": 1,
        "status": "FAIL" if errors else ("WARNING" if warnings else "PASS"),
        "errors": errors,
        "warnings": warnings,
    }
    if args.json_out:
        out = Path(args.json_out)
        if not out.is_absolute():
            out = root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    for item in warnings:
        print(f"WARNING: {item}")
    for item in errors:
        print(f"ERROR: {item}")
    print(f"FLOW_MODEL_STATUS={result['status']} errors={len(errors)} warnings={len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
