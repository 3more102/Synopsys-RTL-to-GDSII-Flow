#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_relative(raw: str) -> Path:
    p = Path(raw)
    if not raw or p.is_absolute() or ".." in p.parts:
        raise ValueError(f"unsafe package-relative path: {raw!r}")
    return p


def parse_checksums(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or not HEX64.match(parts[0]):
            raise ValueError(f"invalid checksums.txt line {lineno}: {raw!r}")
        rel = parts[1].strip()
        if rel.startswith("*"):
            rel = rel[1:]
        if rel.startswith("./"):
            rel = rel[2:]
        rel_path = safe_relative(rel)
        key = rel_path.as_posix()
        if key in result:
            raise ValueError(f"duplicate checksum entry: {key}")
        result[key] = parts[0].lower()
    return result


def verify(delivery: Path, strict_extra: bool = False, require_qualified: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = delivery / "RELEASE_MANIFEST.json"
    checksums_path = delivery / "checksums.txt"

    if not delivery.is_dir():
        return {"schema_version": 1, "status": "FAIL", "errors": [f"delivery directory missing: {delivery}"], "warnings": [], "checked_manifest_artifacts": 0, "checked_checksums": 0}
    if not manifest_path.is_file():
        errors.append("RELEASE_MANIFEST.json is missing")
    if not checksums_path.is_file():
        errors.append("checksums.txt is missing")
    if errors:
        return {"schema_version": 1, "status": "FAIL", "errors": errors, "warnings": warnings, "checked_manifest_artifacts": 0, "checked_checksums": 0}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"schema_version": 1, "status": "FAIL", "errors": [f"cannot parse RELEASE_MANIFEST.json: {exc}"], "warnings": [], "checked_manifest_artifacts": 0, "checked_checksums": 0}

    if manifest.get("schema_version") != 1:
        errors.append(f"unsupported RELEASE_MANIFEST schema_version={manifest.get('schema_version')!r}")
    artifacts = manifest.get("artifacts", [])
    if not isinstance(artifacts, list):
        errors.append("RELEASE_MANIFEST artifacts must be a list")
        artifacts = []

    manifest_paths: set[str] = set()
    checked_manifest = 0
    for item in artifacts:
        if not isinstance(item, dict):
            errors.append("RELEASE_MANIFEST contains a non-object artifact entry")
            continue
        raw_path = str(item.get("path", ""))
        try:
            rel = safe_relative(raw_path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        key = rel.as_posix()
        if key in manifest_paths:
            errors.append(f"duplicate RELEASE_MANIFEST artifact: {key}")
            continue
        manifest_paths.add(key)
        path = delivery / rel
        if not path.is_file():
            errors.append(f"manifest artifact missing: {key}")
            continue
        expected_size = item.get("size")
        expected_hash = str(item.get("sha256", "")).lower()
        if not isinstance(expected_size, int) or expected_size < 0:
            errors.append(f"invalid manifest size for {key}: {expected_size!r}")
        elif path.stat().st_size != expected_size:
            errors.append(f"size mismatch for {key}: expected={expected_size} actual={path.stat().st_size}")
        if not HEX64.match(expected_hash):
            errors.append(f"invalid manifest SHA256 for {key}")
        else:
            actual_hash = sha256_file(path)
            if actual_hash != expected_hash:
                errors.append(f"manifest SHA256 mismatch for {key}: expected={expected_hash} actual={actual_hash}")
        checked_manifest += 1

    try:
        checksums = parse_checksums(checksums_path)
    except (OSError, ValueError) as exc:
        errors.append(f"cannot parse checksums.txt: {exc}")
        checksums = {}

    checked_checksums = 0
    for key, expected_hash in checksums.items():
        path = delivery / key
        if not path.is_file():
            errors.append(f"checksum target missing: {key}")
            continue
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            errors.append(f"checksums.txt mismatch for {key}: expected={expected_hash} actual={actual_hash}")
        checked_checksums += 1

    expected_checksum_paths = set(manifest_paths) | {"RELEASE_MANIFEST.json"}
    missing_checksum_entries = sorted(expected_checksum_paths - set(checksums))
    for key in missing_checksum_entries:
        errors.append(f"checksums.txt missing required entry: {key}")

    current_files = {
        p.relative_to(delivery).as_posix()
        for p in delivery.rglob("*")
        if p.is_file()
    }
    expected_files = manifest_paths | {"RELEASE_MANIFEST.json", "checksums.txt"}
    extras = sorted(current_files - expected_files)
    if extras:
        message = "unexpected package files not represented by RELEASE_MANIFEST: " + ", ".join(extras)
        if strict_extra:
            errors.append(message)
        else:
            warnings.append(message)

    checksum_extras = sorted(set(checksums) - expected_checksum_paths)
    if checksum_extras:
        message = "checksums.txt contains entries absent from RELEASE_MANIFEST: " + ", ".join(checksum_extras)
        if strict_extra:
            errors.append(message)
        else:
            warnings.append(message)

    foundry = str(manifest.get("foundry_signoff", "UNKNOWN"))
    if require_qualified and foundry != "PASS":
        errors.append(f"qualified delivery required but foundry_signoff={foundry}")

    return {
        "schema_version": 1,
        "status": "FAIL" if errors else ("WARNING" if warnings else "PASS"),
        "delivery": str(delivery.resolve()),
        "project": manifest.get("project"),
        "top_module": manifest.get("top_module"),
        "provenance_digest": manifest.get("provenance_digest"),
        "foundry_signoff": foundry,
        "checked_manifest_artifacts": checked_manifest,
        "checked_checksums": checked_checksums,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline integrity verification for an ASIC final_delivery package.")
    ap.add_argument("--delivery", default=".", help="Package directory containing RELEASE_MANIFEST.json and checksums.txt.")
    ap.add_argument("--strict-extra", action="store_true", help="Fail when files exist outside the release manifest inventory.")
    ap.add_argument("--require-qualified", action="store_true", help="Also require RELEASE_MANIFEST foundry_signoff=PASS.")
    ap.add_argument("--report", help="Optional path for machine-readable verification JSON; kept outside the package by default.")
    args = ap.parse_args()

    delivery = Path(args.delivery).resolve()
    result = verify(delivery, strict_extra=args.strict_extra, require_qualified=args.require_qualified)
    if args.report:
        report = Path(args.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for warning in result.get("warnings", []):
        print(f"WARNING: {warning}")
    for error in result.get("errors", []):
        print(f"ERROR: {error}", file=sys.stderr)
    print(
        f"DELIVERY_INTEGRITY={result['status']} "
        f"manifest_artifacts={result.get('checked_manifest_artifacts', 0)} "
        f"checksums={result.get('checked_checksums', 0)} "
        f"foundry_signoff={result.get('foundry_signoff', 'UNKNOWN')}"
    )
    return 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
