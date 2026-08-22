#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "config" / "artifact_provenance.json"
DEFAULT_GRAPH = ROOT / "config" / "stage_graph.json"
DEFAULT_OUTPUT = ROOT / "reports" / "provenance" / "artifact_manifest.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def substitute(pattern: str, project: str) -> str:
    return pattern.replace("${PROJECT_NAME}", project)


def canonical_stage(name: str, contract: dict[str, Any], graph: dict[str, Any]) -> str:
    name = contract.get("aliases", {}).get(name, name)
    return graph.get("aliases", {}).get(name, name)


def git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "N/A"


def read_status(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {"status": "UNKNOWN", "detail": "evidence file missing"}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    values.setdefault("status", "UNKNOWN")
    return values


def load_runtime(root: Path, stage: str) -> dict[str, Any]:
    path = root / "reports" / "runtime" / f"{stage}.latest.json"
    if not path.is_file():
        return {"path": "", "available": False}
    try:
        data = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {"path": str(path.relative_to(root)), "available": False, "error": str(exc)}
    wanted = {
        "flow_run_id",
        "tool",
        "tool_path",
        "script",
        "start",
        "end",
        "duration_seconds",
        "exit_code",
        "git_commit",
        "git_dirty",
        "input_fingerprint",
        "input_digest",
    }
    result = {key: data.get(key) for key in wanted}
    result.update({"path": str(path.relative_to(root)), "available": True})
    return result


def fingerprint_info(root: Path, graph: dict[str, Any], stage: str) -> dict[str, Any]:
    cfg = graph.get("stages", {}).get(stage, {})
    name = cfg.get("fingerprint", stage)
    path = root / "checkpoints" / "fingerprints" / f"{name}.json"
    if not path.is_file():
        return {"name": name, "path": str(path.relative_to(root)), "available": False, "digest": ""}
    try:
        data = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {"name": name, "path": str(path.relative_to(root)), "available": False, "digest": "", "error": str(exc)}
    return {
        "name": name,
        "path": str(path.relative_to(root)),
        "available": True,
        "digest": data.get("digest", ""),
    }


def upstream_fingerprints(root: Path, graph: dict[str, Any], stage: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for dep in graph.get("stages", {}).get(stage, {}).get("depends_on", []):
        result[dep] = fingerprint_info(root, graph, dep)
    return result


def provenance_digest(root: Path) -> str:
    path = root / "reports" / "provenance" / "run_provenance.json"
    if not path.is_file():
        return ""
    try:
        return str(load_json(path).get("provenance_digest", ""))
    except (OSError, json.JSONDecodeError):
        return ""


def expand_pattern(root: Path, pattern: str) -> list[Path]:
    found: list[Path] = []
    for path in sorted(root.glob(pattern), key=lambda p: p.as_posix()):
        if not path.is_file():
            continue
        if not inside(root, path):
            continue
        found.append(path.resolve())
    return found


def stage_records(root: Path, project: str, contract: dict[str, Any], graph: dict[str, Any], stage: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = contract.get("stages", {}).get(stage)
    if cfg is None:
        return [], {"stage": stage, "configured": False, "artifact_count": 0, "missing_required": [], "unmatched_optional": []}

    runtime = load_runtime(root, stage)
    fp = fingerprint_info(root, graph, stage)
    upstream = upstream_fingerprints(root, graph, stage)
    evidence_rel = graph.get("stages", {}).get(stage, {}).get("evidence", "")
    evidence = read_status(root / evidence_rel) if evidence_rel else {"status": "UNKNOWN", "detail": "no stage evidence configured"}

    by_path: dict[Path, dict[str, Any]] = {}
    missing_required: list[str] = []
    unmatched_optional: list[str] = []

    for artifact_class in ("required", "optional"):
        for raw_pattern in cfg.get(artifact_class, []):
            pattern = substitute(str(raw_pattern), project)
            matches = expand_pattern(root, pattern)
            if not matches:
                if artifact_class == "required":
                    missing_required.append(pattern)
                else:
                    unmatched_optional.append(pattern)
            for path in matches:
                record = by_path.setdefault(path, {"classes": set(), "matched_patterns": set()})
                record["classes"].add(artifact_class)
                record["matched_patterns"].add(pattern)

    records: list[dict[str, Any]] = []
    for path, match in sorted(by_path.items(), key=lambda item: item[0].as_posix()):
        stat = path.stat()
        classes = sorted(match["classes"])
        records.append(
            {
                "path": str(path.relative_to(root)),
                "stage": stage,
                "artifact_class": "required" if "required" in classes else "optional",
                "matched_patterns": sorted(match["matched_patterns"]),
                "size_bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "sha256": sha256_file(path),
                "runtime": runtime,
                "stage_fingerprint": fp,
                "upstream_fingerprints": upstream,
                "status_evidence": evidence_rel,
                "stage_status": evidence.get("status", "UNKNOWN"),
            }
        )

    summary = {
        "stage": stage,
        "configured": True,
        "artifact_count": len(records),
        "required_artifact_count": sum(1 for r in records if r["artifact_class"] == "required"),
        "missing_required": missing_required,
        "unmatched_optional": unmatched_optional,
        "runtime_available": bool(runtime.get("available")),
        "fingerprint_available": bool(fp.get("available")),
        "stage_status": evidence.get("status", "UNKNOWN"),
        "status_evidence": evidence_rel,
    }
    return records, summary


def build_manifest(
    root: Path,
    contract: dict[str, Any],
    graph: dict[str, Any],
    project: str,
    requested_stage: str | None,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if contract.get("schema_version") != 1:
        raise ValueError(f"unsupported artifact provenance schema_version={contract.get('schema_version')!r}")
    if graph.get("schema_version") != 2:
        raise ValueError(f"unsupported stage graph schema_version={graph.get('schema_version')!r}")

    stages = contract.get("stages", {})
    if requested_stage:
        stage = canonical_stage(requested_stage, contract, graph)
        selected = [stage]
    else:
        selected = list(stages)

    prior_artifacts = [] if not existing else list(existing.get("artifacts", []))
    prior_summaries = {} if not existing else dict(existing.get("stages", {}))
    replace = set(selected)
    artifacts = [item for item in prior_artifacts if item.get("stage") not in replace]
    summaries = {key: value for key, value in prior_summaries.items() if key not in replace}

    for stage in selected:
        records, summary = stage_records(root, project, contract, graph, stage)
        artifacts.extend(records)
        summaries[stage] = summary

    artifacts.sort(key=lambda item: (item.get("stage", ""), item.get("path", "")))
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": project,
        "git_commit": git_commit(root),
        "run_provenance_digest": provenance_digest(root),
        "artifacts": artifacts,
        "stages": summaries,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build auditable per-artifact lineage from stage runtime/fingerprint evidence.")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    ap.add_argument("--graph", default=str(DEFAULT_GRAPH))
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT))
    ap.add_argument("--stage", help="Refresh one stage and preserve manifest entries for other stages.")
    ap.add_argument("--strict-required", action="store_true", help="Fail when a configured required artifact for the selected scope is absent.")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    contract_path = Path(args.contract).resolve()
    graph_path = Path(args.graph).resolve()
    output = Path(args.output).resolve()
    project = os.environ.get("PROJECT_NAME", "MIPS_16")

    try:
        contract = load_json(contract_path)
        graph = load_json(graph_path)
        existing = load_json(output) if args.stage and output.is_file() else None
        manifest = build_manifest(root, contract, graph, project, args.stage, existing=existing)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    atomic_json(output, manifest)
    canonical = canonical_stage(args.stage, contract, graph) if args.stage else None
    summaries = manifest.get("stages", {})
    scoped = {canonical: summaries.get(canonical, {})} if canonical else summaries
    missing = [f"{stage}:{pattern}" for stage, summary in scoped.items() for pattern in summary.get("missing_required", [])]

    if canonical and canonical not in contract.get("stages", {}):
        print(f"ARTIFACT_PROVENANCE_STATUS=SKIP stage={canonical} reason=no_contract")
    else:
        print(f"ARTIFACT_PROVENANCE={output}")
        print(f"ARTIFACT_PROVENANCE_ARTIFACTS={len(manifest.get('artifacts', []))}")
        print(f"ARTIFACT_PROVENANCE_MISSING_REQUIRED={len(missing)}")

    if args.strict_required and missing:
        for item in missing:
            print(f"MISSING_REQUIRED_ARTIFACT={item}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
