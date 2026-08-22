#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stage_fingerprint import canonical_json, external_path_identity, sha256_file

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "provenance_policy.json"
DEFAULT_OUT = ROOT / "reports" / "provenance" / "run_provenance.json"


def expand(root: Path, patterns: list[str]) -> list[Path]:
    found: set[Path] = set()
    for pattern in patterns:
        for raw in glob.glob(str(root / pattern), recursive=True):
            p = Path(raw)
            if p.is_file() and ".git" not in p.parts:
                found.add(p.resolve())
    return sorted(found)


def file_records(root: Path, patterns: list[str]) -> list[dict[str, Any]]:
    records = []
    for p in expand(root, patterns):
        records.append({
            "path": str(p.relative_to(root)),
            "size": p.stat().st_size,
            "sha256": sha256_file(p),
        })
    return records


def tool_identity(name: str, capability_dir: Path) -> dict[str, Any]:
    value = os.environ.get(name, "")
    if not value:
        defaults = {"DC_SHELL":"dc_shell", "ICC2_SHELL":"icc2_shell", "PT_SHELL":"pt_shell", "FM_SHELL":"fm_shell", "STARRC":"StarXtract", "ICV":"icv"}
        value = defaults.get(name, "")
    resolved = shutil.which(value) if value else None
    out: dict[str, Any] = {"configured": value, "resolved": resolved or "", "exists": bool(resolved)}
    if resolved:
        try:
            p = Path(resolved).resolve(); st = p.stat()
            out.update({"path": str(p), "size": st.st_size, "mtime_ns": st.st_mtime_ns})
        except OSError as exc:
            out["stat_error"] = str(exc)
    kind = {"DC_SHELL":"dc", "ICC2_SHELL":"icc2", "PT_SHELL":"pt", "FM_SHELL":"fm"}.get(name)
    if kind:
        cap = capability_dir / f"{kind}.json"
        if cap.is_file():
            try:
                data = json.loads(cap.read_text())
                out["reported_version"] = data.get("tool_version", "UNKNOWN")
                out["capability_status"] = data.get("status", "UNKNOWN")
            except Exception as exc:
                out["capability_parse_error"] = str(exc)
    return out


def git_info(root: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL, text=True).strip()
    try:
        commit = run("rev-parse", "HEAD")
        branch = run("rev-parse", "--abbrev-ref", "HEAD")
        status = run("status", "--porcelain=v1")
        dirty = bool(status)
        diff = subprocess.check_output(["git", "-C", str(root), "diff", "--binary", "HEAD"], stderr=subprocess.DEVNULL)
        return {"available": True, "commit": commit, "branch": branch, "dirty": dirty, "dirty_diff_sha256": hashlib.sha256(diff).hexdigest() if dirty else ""}
    except Exception:
        return {"available": False, "commit": "N/A", "branch": "N/A", "dirty": "N/A", "dirty_diff_sha256": ""}


def digest_payload(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def build(root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    if policy.get("schema_version") != 1:
        raise ValueError("unsupported provenance policy schema")
    ext_mode = os.environ.get("PROVENANCE_EXTERNAL_PATH_MODE", policy.get("external_path_mode", "stat"))
    groups: dict[str, Any] = {}
    capability_dir = root / "reports" / "capabilities"
    for group_name, cfg in policy.get("groups", {}).items():
        files = file_records(root, cfg.get("files", []))
        env_names = cfg.get("env", [])
        env = {name: os.environ.get(name, "") for name in env_names}
        external = {}
        for name in cfg.get("external_env_paths", []):
            value = os.environ.get(name, "")
            external[name] = {"value": value, "identity": external_path_identity(value, ext_mode)}
        data: dict[str, Any] = {"files": files, "environment": env, "external_paths": external}
        if group_name == "execution":
            tool_vars = [n for n in env_names if n in {"DC_SHELL","ICC2_SHELL","PT_SHELL","FM_SHELL","STARRC","ICV"}]
            data["tools"] = {name: tool_identity(name, capability_dir) for name in tool_vars}
        data["digest"] = digest_payload(data)
        groups[group_name] = data
    git = git_info(root)
    host = {
        "hostname": platform.node(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
    }
    overall_material = {name: groups[name]["digest"] for name in sorted(groups)}
    overall_digest = digest_payload(overall_material)
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project": os.environ.get("PROJECT_NAME", "MIPS_16"),
        "top_module": os.environ.get("TOP_MODULE", "mips_16"),
        "external_path_mode": ext_mode,
        "groups": groups,
        "group_digests": overall_material,
        "provenance_digest": overall_digest,
        "git": git,
        "host": host,
        "notes": [
            "Repository files are content-hashed.",
            "External directories are stat-identified; set PROVENANCE_EXTERNAL_PATH_MODE=sha256 to hash external regular files when practical.",
            "Git commit/dirty metadata is recorded but the content-based group digests are the reproducibility identity."
        ]
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build machine-readable ASIC run provenance.")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--policy", default=str(DEFAULT_POLICY))
    ap.add_argument("--output", default=str(DEFAULT_OUT))
    ap.add_argument("--require-clean-git", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve(); policy = json.loads(Path(args.policy).read_text())
    result = build(root, policy)
    out = Path(args.output).resolve(); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    digest_file = out.with_suffix(".sha256")
    digest_file.write_text(f"{result['provenance_digest']}  {out.name}\n")
    print(f"PROVENANCE digest={result['provenance_digest']} output={out}")
    require_clean = args.require_clean_git or os.environ.get("REQUIRE_CLEAN_GIT", "0") == "1"
    if require_clean and result["git"].get("dirty") is True:
        print("ERROR: Git worktree is dirty and clean Git state is required.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
