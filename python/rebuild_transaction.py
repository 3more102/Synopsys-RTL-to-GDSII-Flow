#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = 1
TERMINAL_STATES = {"APPLIED", "ROLLED_BACK", "RESTORED"}


class TransactionError(RuntimeError):
    pass


def _inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def path_identity(path: Path) -> dict[str, Any]:
    """Return an inexpensive but auditable identity for an archive source.

    Files are content hashed. Directories intentionally use a structural digest
    (relative path, type, size, mtime) rather than hashing every database byte;
    ICC2 databases can be very large and archive verification must not turn into
    a second full database copy/read pass.
    """
    if not path.exists():
        return {"exists": False}
    if path.is_file():
        st = path.stat()
        return {
            "exists": True,
            "kind": "file",
            "size": st.st_size,
            "mtime_ns": st.st_mtime_ns,
            "sha256": _sha256_file(path),
        }

    entries: list[str] = []
    files = 0
    dirs = 0
    total_bytes = 0
    for item in sorted(path.rglob("*"), key=lambda p: p.as_posix()):
        rel = item.relative_to(path).as_posix()
        st = item.stat()
        if item.is_dir():
            dirs += 1
            entries.append(f"D\t{rel}\t{st.st_mtime_ns}")
        elif item.is_file():
            files += 1
            total_bytes += st.st_size
            entries.append(f"F\t{rel}\t{st.st_size}\t{st.st_mtime_ns}")
        else:
            entries.append(f"O\t{rel}\t{st.st_size}\t{st.st_mtime_ns}")
    digest = hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()
    return {
        "exists": True,
        "kind": "directory",
        "file_count": files,
        "directory_count": dirs,
        "total_bytes": total_bytes,
        "structural_sha256": digest,
    }


def identities_equivalent(before: dict[str, Any], after: dict[str, Any]) -> bool:
    if before.get("kind") != after.get("kind"):
        return False
    if before.get("kind") == "file":
        return before.get("size") == after.get("size") and before.get("sha256") == after.get("sha256")
    if before.get("kind") == "directory":
        return (
            before.get("file_count") == after.get("file_count")
            and before.get("directory_count") == after.get("directory_count")
            and before.get("total_bytes") == after.get("total_bytes")
            and before.get("structural_sha256") == after.get("structural_sha256")
        )
    return False


def _validate_actions(root: Path, actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_sources: set[Path] = set()
    seen_destinations: set[Path] = set()
    for index, raw in enumerate(actions):
        src = Path(raw["source"]).resolve()
        dst = Path(raw["destination"]).resolve()
        if not _inside(root, src) or not _inside(root, dst):
            raise TransactionError(f"action {index}: source/destination must remain inside project root")
        if src == dst:
            raise TransactionError(f"action {index}: source equals destination: {src}")
        if src in seen_sources:
            raise TransactionError(f"duplicate source in transaction: {src}")
        if dst in seen_destinations:
            raise TransactionError(f"duplicate destination in transaction: {dst}")
        if not src.exists():
            raise TransactionError(f"source disappeared before transaction: {src}")
        if dst.exists():
            raise TransactionError(f"archive destination already exists: {dst}")
        seen_sources.add(src)
        seen_destinations.add(dst)
        item = dict(raw)
        item["source"] = str(src)
        item["destination"] = str(dst)
        item["pre_identity"] = path_identity(src)
        item["applied"] = False
        normalized.append(item)
    return normalized


def _move(action: dict[str, Any], move_func: Callable[[str, str], Any] = shutil.move) -> None:
    src = Path(action["source"])
    dst = Path(action["destination"])
    dst.parent.mkdir(parents=True, exist_ok=True)
    move_func(str(src), str(dst))
    if action.get("type") == "database":
        src.mkdir(parents=True, exist_ok=True)
    post = path_identity(dst)
    if not identities_equivalent(action["pre_identity"], post):
        raise TransactionError(f"archive verification failed after moving {src} -> {dst}")
    action["post_identity"] = post
    action["applied"] = True


def _restore_one(action: dict[str, Any], move_func: Callable[[str, str], Any] = shutil.move) -> None:
    src = Path(action["source"])
    dst = Path(action["destination"])
    if not dst.exists():
        raise TransactionError(f"archive payload missing during restore: {dst}")
    if action.get("type") == "database" and src.is_dir() and not any(src.iterdir()):
        src.rmdir()
    elif src.exists():
        raise TransactionError(f"restore would overwrite current data: {src}")
    src.parent.mkdir(parents=True, exist_ok=True)
    move_func(str(dst), str(src))
    restored = path_identity(src)
    if not identities_equivalent(action["pre_identity"], restored):
        raise TransactionError(f"restore verification failed for {src}")
    action["applied"] = False
    action["restored_identity"] = restored


def apply_transaction(
    root: Path,
    actions: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
    transaction_root: Path | None = None,
    move_func: Callable[[str, str], Any] = shutil.move,
) -> Path:
    root = root.resolve()
    tx_root = (transaction_root or root / "checkpoints" / "rebuild_transactions").resolve()
    if not _inside(root, tx_root):
        raise TransactionError("transaction root must remain inside project root")
    normalized = _validate_actions(root, actions)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    tx_dir = tx_root / f"{stamp}_{os.getpid()}"
    manifest = tx_dir / "transaction.json"
    data: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "transaction_id": tx_dir.name,
        "state": "PREPARED",
        "created_at": datetime.now().astimezone().isoformat(),
        "updated_at": datetime.now().astimezone().isoformat(),
        "metadata": metadata or {},
        "actions": normalized,
        "error": None,
    }
    _atomic_json(manifest, data)

    completed: list[dict[str, Any]] = []
    data["state"] = "APPLYING"
    data["updated_at"] = datetime.now().astimezone().isoformat()
    _atomic_json(manifest, data)
    try:
        for action in data["actions"]:
            _move(action, move_func=move_func)
            completed.append(action)
            data["updated_at"] = datetime.now().astimezone().isoformat()
            _atomic_json(manifest, data)
    except Exception as exc:
        data["state"] = "ROLLING_BACK"
        data["error"] = f"{type(exc).__name__}: {exc}"
        data["updated_at"] = datetime.now().astimezone().isoformat()
        _atomic_json(manifest, data)
        rollback_errors: list[str] = []
        for action in reversed(completed):
            try:
                _restore_one(action, move_func=move_func)
            except Exception as rollback_exc:
                rollback_errors.append(f"{action['source']}: {rollback_exc}")
        data["rollback_errors"] = rollback_errors
        data["state"] = "ROLLED_BACK" if not rollback_errors else "ROLLBACK_FAILED"
        data["updated_at"] = datetime.now().astimezone().isoformat()
        _atomic_json(manifest, data)
        raise TransactionError(f"transaction failed; state={data['state']}; manifest={manifest}: {exc}") from exc

    data["state"] = "APPLIED"
    data["updated_at"] = datetime.now().astimezone().isoformat()
    _atomic_json(manifest, data)
    return manifest


def restore_transaction(manifest: Path, move_func: Callable[[str, str], Any] = shutil.move) -> Path:
    manifest = manifest.resolve()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise TransactionError(f"unsupported transaction schema_version={data.get('schema_version')}")
    if data.get("state") != "APPLIED":
        raise TransactionError(f"only APPLIED transactions can be restored; current state={data.get('state')}")

    # Preflight every source before moving anything back.
    for action in data.get("actions", []):
        src = Path(action["source"])
        dst = Path(action["destination"])
        if not dst.exists():
            raise TransactionError(f"archive payload missing: {dst}")
        if action.get("type") == "database" and src.is_dir() and not any(src.iterdir()):
            continue
        if src.exists():
            raise TransactionError(f"restore would overwrite current data: {src}")

    data["state"] = "RESTORING"
    data["updated_at"] = datetime.now().astimezone().isoformat()
    _atomic_json(manifest, data)
    restored: list[dict[str, Any]] = []
    try:
        for action in reversed(data.get("actions", [])):
            _restore_one(action, move_func=move_func)
            restored.append(action)
            data["updated_at"] = datetime.now().astimezone().isoformat()
            _atomic_json(manifest, data)
    except Exception as exc:
        data["state"] = "RESTORE_FAILED"
        data["error"] = f"{type(exc).__name__}: {exc}"
        data["updated_at"] = datetime.now().astimezone().isoformat()
        _atomic_json(manifest, data)
        raise TransactionError(f"restore failed; manual recovery required; manifest={manifest}: {exc}") from exc

    data["state"] = "RESTORED"
    data["restored_at"] = datetime.now().astimezone().isoformat()
    data["updated_at"] = data["restored_at"]
    _atomic_json(manifest, data)
    return manifest
