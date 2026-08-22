#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / "reports" / "summary" / "rebuild_plan.json"


def inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def safe_evidence(root: Path, rel: str) -> Path:
    if not rel:
        raise ValueError("empty evidence path")
    path = root / rel
    if not inside(root, path):
        raise ValueError(f"evidence escapes project root: {rel}")
    allowed = (root / "checkpoints", root / "reports" / "status")
    if not any(inside(base, path) for base in allowed):
        raise ValueError(f"refusing to invalidate non-evidence path: {rel}")
    return path


def load_plan(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 2:
        raise ValueError(f"unsupported rebuild plan schema_version={data.get('schema_version')!r}; expected 2")
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description="Safely archive stale ASIC stage evidence before executing a rebuild plan.")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--plan", default=str(DEFAULT_PLAN))
    ap.add_argument("--apply", action="store_true", help="Actually archive evidence. Without this flag the command is a dry run.")
    ap.add_argument("--archive-database", action="store_true", help="Move an existing database/ aside when the plan requires ICC2 re-initialization.")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    plan_path = Path(args.plan)
    if not plan_path.is_absolute():
        plan_path = root / plan_path
    try:
        plan = load_plan(plan_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    selected = [row for row in plan.get("stages", []) if row.get("rebuild_required")]
    if not selected:
        print("No rebuild evidence needs invalidation.")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = root / "checkpoints" / "stale_archive" / stamp
    db_archive = root / "runs" / "stale_database_archive" / stamp / "database"
    actions: list[dict] = []

    for row in selected:
        rel = row.get("evidence", "")
        try:
            src = safe_evidence(root, rel)
        except ValueError as exc:
            print(f"ERROR: stage={row.get('stage')} {exc}", file=sys.stderr)
            return 2
        if src.exists():
            dst = archive / rel
            actions.append({"type": "evidence", "stage": row.get("stage"), "source": str(src), "destination": str(dst)})

    requires_init = any(row.get("stage") == "icc2_init" for row in selected)
    database = root / "database"
    database_nonempty = database.is_dir() and any(database.iterdir())
    if requires_init and database_nonempty:
        if not args.archive_database:
            print("ERROR: rebuild plan includes icc2_init while database/ is non-empty.", file=sys.stderr)
            print("Re-running create_lib against the existing design library may be unsafe or fail.", file=sys.stderr)
            print("Re-run with --archive-database to move database/ into a timestamped archive before rebuilding.", file=sys.stderr)
            return 78
        actions.append({"type": "database", "stage": "icc2_init", "source": str(database), "destination": str(db_archive)})

    mode = "APPLY" if args.apply else "DRY_RUN"
    print(f"REBUILD_INVALIDATION_MODE={mode}")
    for action in actions:
        print(f"{action['type'].upper()} {action['source']} -> {action['destination']}")

    if not args.apply:
        print("No files were moved. Re-run with --apply after reviewing the plan.")
        return 0

    for action in actions:
        src = Path(action["source"])
        dst = Path(action["destination"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        if action["type"] == "database":
            if dst.exists():
                print(f"ERROR: database archive destination already exists: {dst}", file=sys.stderr)
                return 79
            shutil.move(str(src), str(dst))
            database.mkdir(parents=True, exist_ok=True)
        else:
            if src.exists():
                shutil.move(str(src), str(dst))

    archive.mkdir(parents=True, exist_ok=True)
    manifest = archive / "invalidation_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "created_at": datetime.now().astimezone().isoformat(),
                "pid": os.getpid(),
                "source_plan": str(plan_path),
                "earliest_rebuild_stage": plan.get("earliest_rebuild_stage"),
                "execution_targets": plan.get("execution_targets", []),
                "actions": actions,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"INVALIDATION_ARCHIVE={archive}")
    print(f"INVALIDATION_MANIFEST={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
