#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK_ROOT = ROOT / "work" / "locks"
DEFAULT_ARCHIVE_ROOT = ROOT / "work" / "stale_locks"
OWNER_FILE = "owner.json"


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def inside(base: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def boot_id() -> str:
    path = Path("/proc/sys/kernel/random/boot_id")
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def process_start_ticks(pid: int) -> str:
    """Return Linux /proc process start ticks or empty string when unavailable."""
    path = Path(f"/proc/{pid}/stat")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    close = text.rfind(")")
    if close < 0:
        return ""
    fields = text[close + 2 :].split()
    # fields[0] is stat field 3, therefore field 22 is index 19 here.
    return fields[19] if len(fields) > 19 else ""


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def owner_record(
    stage: str,
    tool: str,
    script: str,
    flow_run_id: str,
    pid: int | None = None,
    ppid: int | None = None,
) -> dict[str, Any]:
    owner_pid = os.getpid() if pid is None else int(pid)
    owner_ppid = os.getppid() if ppid is None else int(ppid)
    return {
        "schema_version": 1,
        "stage": stage,
        "pid": owner_pid,
        "ppid": owner_ppid,
        "hostname": socket.gethostname(),
        "boot_id": boot_id(),
        "process_start_ticks": process_start_ticks(owner_pid),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "script": script,
        "flow_run_id": flow_run_id,
        "project_root": str(ROOT),
    }


def write_owner(
    lock_dir: Path,
    stage: str,
    tool: str,
    script: str,
    flow_run_id: str,
    pid: int | None = None,
    ppid: int | None = None,
) -> Path:
    lock_dir = lock_dir.resolve()
    if not lock_dir.is_dir():
        raise ValueError(f"lock directory does not exist: {lock_dir}")
    if not inside(DEFAULT_LOCK_ROOT, lock_dir):
        raise ValueError(f"refusing to write owner outside {DEFAULT_LOCK_ROOT}: {lock_dir}")
    path = lock_dir / OWNER_FILE
    atomic_json(path, owner_record(stage, tool, script, flow_run_id, pid=pid, ppid=ppid))
    return path


def load_owner(lock_dir: Path) -> tuple[dict[str, Any] | None, str]:
    path = lock_dir / OWNER_FILE
    if not path.is_file():
        return None, "owner.json missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"owner.json unreadable: {exc}"
    if data.get("schema_version") != 1:
        return None, f"unsupported owner schema_version={data.get('schema_version')!r}"
    return data, ""


def inspect_lock(lock_dir: Path) -> dict[str, Any]:
    """Classify lock ownership conservatively.

    STALE is reserved for a condition that proves processes from the recorded
    owner cannot still exist: a different boot identity on the same host.
    A dead/reused shell PID during the same boot remains UNKNOWN because an EDA
    child could have survived its parent. UNKNOWN requires explicit engineer
    action and is never auto-recovered by run_stage.sh.
    """
    lock_dir = lock_dir.resolve()
    local_host = socket.gethostname()
    local_boot = boot_id()
    base = {
        "lock": str(lock_dir),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "local_hostname": local_host,
        "local_boot_id": local_boot,
    }
    if not lock_dir.exists():
        return {**base, "state": "FREE", "reason": "lock directory absent", "owner": None}
    if not lock_dir.is_dir():
        return {**base, "state": "UNKNOWN", "reason": "lock path exists but is not a directory", "owner": None}

    owner, error = load_owner(lock_dir)
    if owner is None:
        return {**base, "state": "UNKNOWN", "reason": error, "owner": None}

    owner_host = str(owner.get("hostname", ""))
    if not owner_host:
        return {**base, "state": "UNKNOWN", "reason": "owner hostname missing", "owner": owner}
    if owner_host != local_host:
        return {
            **base,
            "state": "FOREIGN_HOST",
            "reason": f"lock belongs to host {owner_host}; local host is {local_host}",
            "owner": owner,
        }

    owner_boot = str(owner.get("boot_id", ""))
    if owner_boot and local_boot and owner_boot != local_boot:
        return {
            **base,
            "state": "STALE",
            "reason": "same host name but boot identity changed; no process from the recorded boot can still be running",
            "owner": owner,
        }

    try:
        owner_pid = int(owner.get("pid", 0))
    except (TypeError, ValueError):
        return {**base, "state": "UNKNOWN", "reason": "owner PID is invalid", "owner": owner}
    if owner_pid <= 0:
        return {**base, "state": "UNKNOWN", "reason": "owner PID is missing/non-positive", "owner": owner}
    if not pid_alive(owner_pid):
        return {
            **base,
            "state": "UNKNOWN",
            "reason": f"runner PID {owner_pid} is not alive during the same boot; an EDA child may have survived",
            "owner": owner,
        }

    recorded_start = str(owner.get("process_start_ticks", ""))
    current_start = process_start_ticks(owner_pid)
    if recorded_start and current_start and recorded_start != current_start:
        return {
            **base,
            "state": "UNKNOWN",
            "reason": f"PID {owner_pid} was reused during the same boot; child-process state is not proven",
            "owner": owner,
        }

    return {
        **base,
        "state": "ACTIVE",
        "reason": f"owner PID {owner_pid} is alive on the local host",
        "owner": owner,
    }


def archive_destination(archive_root: Path, lock_dir: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return archive_root / f"{stamp}_{lock_dir.name}"


def recover_lock(
    lock_dir: Path,
    archive_root: Path = DEFAULT_ARCHIVE_ROOT,
    allow_unknown: bool = False,
) -> Path:
    lock_dir = lock_dir.resolve()
    archive_root = archive_root.resolve()
    if not inside(DEFAULT_LOCK_ROOT, lock_dir):
        raise ValueError(f"refusing recovery outside lock root: {lock_dir}")
    if not inside(ROOT / "work", archive_root):
        raise ValueError(f"archive root must stay under {ROOT / 'work'}: {archive_root}")
    info = inspect_lock(lock_dir)
    state = info["state"]
    permitted = state == "STALE" or (allow_unknown and state == "UNKNOWN")
    if not permitted:
        raise RuntimeError(f"lock is not recoverable under requested policy: state={state} reason={info['reason']}")
    if state == "UNKNOWN" and not allow_unknown:
        raise RuntimeError("UNKNOWN locks require explicit --force-unknown")
    archive_root.mkdir(parents=True, exist_ok=True)
    destination = archive_destination(archive_root, lock_dir)
    if destination.exists():
        raise RuntimeError(f"stale-lock archive destination already exists: {destination}")
    shutil.move(str(lock_dir), str(destination))
    atomic_json(
        destination / "recovery.json",
        {
            "schema_version": 1,
            "recovered_at": datetime.now(timezone.utc).isoformat(),
            "original_lock": str(lock_dir),
            "inspection": info,
            "recovery": "archived_not_deleted",
            "forced_unknown": bool(state == "UNKNOWN" and allow_unknown),
        },
    )
    return destination


def iter_locks(lock_root: Path) -> list[Path]:
    if not lock_root.is_dir():
        return []
    return sorted((p for p in lock_root.iterdir() if p.name.endswith(".lock")), key=lambda p: p.name)


def print_info(info: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(info, indent=2, sort_keys=True))
        return
    print(f"LOCK_STATE={info['state']}")
    print(f"LOCK_PATH={info['lock']}")
    print(f"LOCK_REASON={info['reason']}")
    owner = info.get("owner") or {}
    if owner:
        print(f"LOCK_STAGE={owner.get('stage', '')}")
        print(f"LOCK_PID={owner.get('pid', '')}")
        print(f"LOCK_HOST={owner.get('hostname', '')}")
        print(f"LOCK_RUN_ID={owner.get('flow_run_id', '')}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Inspect and safely recover ASIC stage lock directories.")
    sub = ap.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record")
    record.add_argument("--lock", required=True)
    record.add_argument("--stage", required=True)
    record.add_argument("--tool", default="")
    record.add_argument("--script", default="")
    record.add_argument("--flow-run-id", default="")
    record.add_argument("--pid", type=int, default=None, help="Owning runner PID; defaults to helper PID only for manual use.")
    record.add_argument("--ppid", type=int, default=None)

    check = sub.add_parser("check")
    check.add_argument("--lock", required=True)
    check.add_argument("--json", action="store_true")

    listing = sub.add_parser("list")
    listing.add_argument("--lock-root", default=str(DEFAULT_LOCK_ROOT))
    listing.add_argument("--json", action="store_true")

    recover = sub.add_parser("recover")
    recover.add_argument("--lock", required=True)
    recover.add_argument("--archive-root", default=str(DEFAULT_ARCHIVE_ROOT))
    recover.add_argument(
        "--force-unknown",
        action="store_true",
        help="Explicitly archive an UNKNOWN local lock after engineer review. ACTIVE and FOREIGN_HOST locks remain protected.",
    )

    args = ap.parse_args()
    try:
        if args.command == "record":
            path = write_owner(
                Path(args.lock),
                args.stage,
                args.tool,
                args.script,
                args.flow_run_id,
                pid=args.pid,
                ppid=args.ppid,
            )
            print(f"LOCK_OWNER={path}")
            return 0
        if args.command == "check":
            print_info(inspect_lock(Path(args.lock)), args.json)
            return 0
        if args.command == "list":
            infos = [inspect_lock(path) for path in iter_locks(Path(args.lock_root))]
            if args.json:
                print(json.dumps(infos, indent=2, sort_keys=True))
            else:
                if not infos:
                    print("No stage locks found.")
                for info in infos:
                    print(f"{Path(info['lock']).name}: {info['state']} - {info['reason']}")
            return 0
        if args.command == "recover":
            destination = recover_lock(
                Path(args.lock),
                Path(args.archive_root),
                allow_unknown=args.force_unknown,
            )
            print(f"STALE_LOCK_ARCHIVE={destination}")
            print("LOCK_RECOVERY=ARCHIVED")
            return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 4
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
