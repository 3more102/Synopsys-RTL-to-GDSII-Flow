#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINES = ROOT / "baselines" / "local"
NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def validate_name(name: str) -> str:
    if not NAME_RE.fullmatch(name) or name in {".", ".."}:
        raise ValueError("baseline name may contain only letters, digits, '.', '_' and '-'")
    return name


def source_files(root: Path, source: str) -> dict[str, Path]:
    if source == "current":
        base = root
    else:
        base = Path(source)
        if not base.is_absolute():
            base = root / base
        base = base.resolve()
    return {
        "qor_summary.json": base / "reports" / "summary" / "qor_summary.json",
        "run_provenance.json": base / "reports" / "provenance" / "run_provenance.json",
        "release_verification.json": base / "reports" / "summary" / "release_verification.json",
        "qor_regression.json": base / "reports" / "summary" / "qor_regression.json",
    }


def release_status(path: Path) -> str:
    data = read_json(path)
    return str(data.get("status", "UNKNOWN")) if isinstance(data, dict) else "UNKNOWN"


def promote(root: Path, baseline_root: Path, name: str, source: str, allow_unverified: bool, replace: bool) -> Path:
    name = validate_name(name)
    files = source_files(root, source)
    required = [files["qor_summary.json"], files["run_provenance.json"]]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise ValueError("required baseline evidence missing: " + ", ".join(missing))

    status = release_status(files["release_verification.json"])
    if status != "PASS" and not allow_unverified:
        raise ValueError(
            f"release verification status is {status}; refusing baseline promotion. "
            "Use --allow-unverified only for an explicitly provisional baseline."
        )

    target = baseline_root / name
    if target.exists():
        if not replace:
            raise ValueError(f"baseline already exists: {target}; use --replace to archive and replace it")
        archive = baseline_root / ".archive" / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name}"
        archive.parent.mkdir(parents=True, exist_ok=True)
        if archive.exists():
            raise ValueError(f"baseline archive destination already exists: {archive}")
        shutil.move(str(target), str(archive))

    target.mkdir(parents=True, exist_ok=False)
    copied: list[dict[str, Any]] = []
    for filename, src in files.items():
        if not src.is_file():
            continue
        dst = target / filename
        shutil.copy2(src, dst)
        copied.append({"path": filename, "size": dst.stat().st_size, "sha256": sha256_file(dst)})

    provenance = read_json(target / "run_provenance.json") or {}
    metadata = {
        "schema_version": 1,
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "release_status": status,
        "provisional": status != "PASS",
        "provenance_digest": provenance.get("provenance_digest", "UNKNOWN") if isinstance(provenance, dict) else "UNKNOWN",
        "git": provenance.get("git", {}) if isinstance(provenance, dict) else {},
        "files": copied,
        "qor_baseline": "qor_summary.json",
        "provenance_baseline": "run_provenance.json",
    }
    (target / "BASELINE.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def verify_baseline(path: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    metadata_path = path / "BASELINE.json"
    data = read_json(metadata_path)
    if not isinstance(data, dict):
        return False, [f"missing or invalid BASELINE.json: {metadata_path}"]
    if data.get("schema_version") != 1:
        errors.append(f"unsupported baseline schema_version={data.get('schema_version')!r}")
    for item in data.get("files", []):
        if not isinstance(item, dict):
            errors.append("invalid file entry in BASELINE.json")
            continue
        rel = str(item.get("path", ""))
        p = path / rel
        if not p.is_file():
            errors.append(f"missing baseline file: {rel}")
            continue
        if p.stat().st_size != item.get("size"):
            errors.append(f"size mismatch: {rel}")
        actual = sha256_file(p)
        if actual != item.get("sha256"):
            errors.append(f"SHA256 mismatch: {rel}")
    return not errors, errors


def list_baselines(baseline_root: Path) -> int:
    if not baseline_root.is_dir():
        print("No local baselines.")
        return 0
    count = 0
    for path in sorted(p for p in baseline_root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        data = read_json(path / "BASELINE.json") or {}
        ok, _ = verify_baseline(path)
        print(
            f"{path.name}\tintegrity={'PASS' if ok else 'FAIL'}\t"
            f"release={data.get('release_status', 'UNKNOWN')}\t"
            f"provenance={data.get('provenance_digest', 'UNKNOWN')}"
        )
        count += 1
    if count == 0:
        print("No local baselines.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Promote, inspect, and verify local ASIC QoR/provenance baselines.")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--baseline-root", default=str(DEFAULT_BASELINES))
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("promote")
    p.add_argument("name")
    p.add_argument("--source", default="current", help="'current' or an archived run directory.")
    p.add_argument("--allow-unverified", action="store_true")
    p.add_argument("--replace", action="store_true")

    sub.add_parser("list")
    p = sub.add_parser("show"); p.add_argument("name")
    p = sub.add_parser("verify"); p.add_argument("name")
    p = sub.add_parser("path"); p.add_argument("name")

    args = ap.parse_args()
    root = Path(args.root).resolve()
    baseline_root = Path(args.baseline_root)
    if not baseline_root.is_absolute():
        baseline_root = root / baseline_root
    baseline_root = baseline_root.resolve()

    try:
        if args.command == "promote":
            path = promote(root, baseline_root, args.name, args.source, args.allow_unverified, args.replace)
            print(f"BASELINE_PROMOTED={path}")
            print(f"QOR_BASELINE={path / 'qor_summary.json'}")
            print(f"PROVENANCE_BASELINE={path / 'run_provenance.json'}")
            return 0
        if args.command == "list":
            return list_baselines(baseline_root)

        name = validate_name(args.name)
        path = baseline_root / name
        if not path.is_dir():
            raise ValueError(f"baseline not found: {path}")
        if args.command == "show":
            print((path / "BASELINE.json").read_text(encoding="utf-8"))
            return 0
        if args.command == "path":
            print(path / "qor_summary.json")
            return 0
        if args.command == "verify":
            ok, errors = verify_baseline(path)
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            print(f"BASELINE_INTEGRITY={'PASS' if ok else 'FAIL'} name={name}")
            return 0 if ok else 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
