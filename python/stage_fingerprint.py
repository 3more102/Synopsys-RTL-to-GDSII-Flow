#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import shlex
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "fingerprint_policy.json"
DEFAULT_OUT = ROOT / "checkpoints" / "fingerprints"


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def load_policy(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if data.get("schema_version") != 1:
        raise ValueError(f"unsupported fingerprint policy schema_version={data.get('schema_version')}")
    return data


def resolve_stage(policy: dict[str, Any], stage: str) -> str:
    return policy.get("aliases", {}).get(stage, stage)


def expand_files(root: Path, patterns: list[str]) -> list[Path]:
    found: set[Path] = set()
    for pattern in patterns:
        for raw in glob.glob(str(root / pattern), recursive=True):
            p = Path(raw)
            if p.is_file():
                found.add(p.resolve())
    return sorted(found)


def external_path_identity(raw_value: str, mode: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not raw_value:
        return results
    try:
        tokens = shlex.split(raw_value)
    except ValueError:
        tokens = [raw_value]
    for token in tokens:
        if token in {"*", "-", "+"}:
            continue
        p = Path(os.path.expandvars(os.path.expanduser(token)))
        item: dict[str, Any] = {"configured": token, "exists": p.exists()}
        if p.exists():
            try:
                rp = p.resolve()
            except OSError:
                rp = p.absolute()
            item["path"] = str(rp)
            try:
                st = rp.stat()
                item.update({"size": st.st_size, "mtime_ns": st.st_mtime_ns, "is_dir": rp.is_dir()})
                if mode == "sha256" and rp.is_file():
                    item["sha256"] = sha256_file(rp)
            except OSError as exc:
                item["stat_error"] = str(exc)
        results.append(item)
    return results


def collect(root: Path, policy: dict[str, Any], requested_stage: str) -> dict[str, Any]:
    stage = resolve_stage(policy, requested_stage)
    stages = policy.get("stages", {})
    if stage not in stages:
        raise KeyError(f"stage '{requested_stage}' resolves to '{stage}', which is not in fingerprint policy")
    cfg = stages[stage]
    file_patterns = list(cfg.get("files", []))
    files = []
    for p in expand_files(root, file_patterns):
        files.append({"path": str(p.relative_to(root)), "size": p.stat().st_size, "sha256": sha256_file(p)})

    env_names = sorted(set(policy.get("common_env", [])) | set(cfg.get("env", [])))
    env = {name: os.environ.get(name, "") for name in env_names}

    ext_names = sorted(set(policy.get("common_external_env_paths", [])) | set(cfg.get("external_env_paths", [])))
    ext_mode = os.environ.get("FINGERPRINT_EXTERNAL_PATH_MODE", policy.get("external_path_mode", "stat"))
    external = {name: {"value": os.environ.get(name, ""), "identity": external_path_identity(os.environ.get(name, ""), ext_mode)} for name in ext_names}

    tool_env = cfg.get("tool_env", "")
    tool_value = os.environ.get(tool_env, "") if tool_env else ""
    tool_path = shutil.which(tool_value) if tool_value else None
    tool: dict[str, Any] = {"env": tool_env, "value": tool_value, "resolved": tool_path or ""}
    if tool_path:
        try:
            st = Path(tool_path).resolve().stat()
            tool.update({"size": st.st_size, "mtime_ns": st.st_mtime_ns})
        except OSError as exc:
            tool["stat_error"] = str(exc)

    body = {"schema_version": 1, "stage": stage, "requested_stage": requested_stage, "file_patterns": file_patterns, "files": files, "environment": env, "external_paths": external, "external_path_mode": ext_mode, "tool": tool}
    digest_body = dict(body)
    digest_body.pop("requested_stage", None)
    digest = hashlib.sha256(canonical_json(digest_body)).hexdigest()
    return {**body, "digest": digest}


def diff_components(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    changed = []
    for key in ("files", "environment", "external_paths", "tool"):
        if old.get(key) != new.get(key):
            changed.append(key)
    if old.get("stage") != new.get("stage"):
        changed.append("stage")
    return changed


def fingerprint_path(out_dir: Path, policy: dict[str, Any], stage: str) -> Path:
    return out_dir / f"{resolve_stage(policy, stage)}.json"


def cmd_capture(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    policy = load_policy(Path(args.policy).resolve())
    resolved = resolve_stage(policy, args.stage)
    if resolved not in policy.get("stages", {}):
        if getattr(args, "if_known", False):
            if not args.quiet:
                print(f"SKIP stage={args.stage} not_in_fingerprint_policy")
            return 0
        raise KeyError(f"stage {args.stage!r} resolves to {resolved!r}, which is not in fingerprint policy")
    data = collect(root, policy, args.stage)
    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    path = fingerprint_path(out, policy, args.stage)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)
    if not args.quiet:
        print(f"CAPTURED stage={data['stage']} digest={data['digest']} file={path}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    policy = load_policy(Path(args.policy).resolve())
    path = fingerprint_path(Path(args.out_dir).resolve(), policy, args.stage)
    if not path.is_file():
        if args.if_present:
            if not args.quiet:
                print(f"UNKNOWN stage={resolve_stage(policy, args.stage)} no_saved_fingerprint")
            return 0
        print(f"MISSING stage={resolve_stage(policy, args.stage)} fingerprint={path}")
        return 4
    old = json.loads(path.read_text())
    new = collect(root, policy, args.stage)
    if old.get("digest") == new.get("digest"):
        if not args.quiet:
            print(f"FRESH stage={new['stage']} digest={new['digest']}")
        return 0
    changed = diff_components(old, new)
    print(f"STALE stage={new['stage']} old={old.get('digest')} new={new.get('digest')} changed={','.join(changed) or 'unknown'}")
    if args.details:
        print(json.dumps({"old": old, "new": new, "changed": changed}, indent=2, sort_keys=True))
    return 3


def cmd_list(args: argparse.Namespace) -> int:
    policy = load_policy(Path(args.policy).resolve())
    for name in sorted(policy.get("stages", {})):
        print(name)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Capture/check deterministic ASIC stage input fingerprints.")
    p.add_argument("--root", default=str(ROOT))
    p.add_argument("--policy", default=str(DEFAULT_POLICY))
    p.add_argument("--out-dir", default=str(DEFAULT_OUT))
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("capture", "check"):
        s = sub.add_parser(name)
        s.add_argument("--stage", required=True)
        s.add_argument("--quiet", action="store_true")
        if name == "capture":
            s.add_argument("--if-known", action="store_true", help="Return success without writing when stage is not in policy.")
        if name == "check":
            s.add_argument("--if-present", action="store_true", help="Return success when no saved fingerprint exists yet.")
            s.add_argument("--details", action="store_true")
    sub.add_parser("list")
    return p


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "capture": return cmd_capture(args)
    if args.command == "check": return cmd_check(args)
    if args.command == "list": return cmd_list(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
