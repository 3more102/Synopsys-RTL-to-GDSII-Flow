#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from rebuild_transaction import TransactionError, apply_transaction, restore_transaction

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


def build_actions(root: Path, plan: dict, archive_database: bool) -> tuple[list[dict], Path]:
    selected = [row for row in plan.get("stages", []) if row.get("rebuild_required")]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = root / "checkpoints" / "stale_archive" / stamp
    db_archive = root / "runs" / "stale_database_archive" / stamp / "database"
    actions: list[dict] = []

    for row in selected:
        rel = row.get("evidence", "")
        if not rel:
            continue
        src = safe_evidence(root, rel)
        if src.exists():
            actions.append(
                {
                    "type": "evidence",
                    "stage": row.get("stage"),
                    "source": str(src),
                    "destination": str(archive / rel),
                }
            )

    requires_init = any(row.get("stage") == "icc2_init" for row in selected)
    database = root / "database"
    database_nonempty = database.is_dir() and any(database.iterdir())
    if requires_init and database_nonempty:
        if not archive_database:
            raise TransactionError(
                "rebuild plan includes icc2_init while database/ is non-empty; "
                "re-run with --archive-database to preserve the existing ICC2 database before rebuilding"
            )
        actions.append(
            {
                "type": "database",
                "stage": "icc2_init",
                "source": str(database),
                "destination": str(db_archive),
            }
        )
    return actions, archive


def main() -> int:
    ap = argparse.ArgumentParser(description="Safely archive/restore stale ASIC stage evidence around a rebuild plan.")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--plan", default=str(DEFAULT_PLAN))
    ap.add_argument("--apply", action="store_true", help="Apply the invalidation transaction. Default is review-only dry run.")
    ap.add_argument("--archive-database", action="store_true", help="Preserve a non-empty database/ when ICC2 re-initialization is required.")
    ap.add_argument("--restore", metavar="TRANSACTION_JSON", help="Restore a previously APPLIED invalidation transaction. Refuses to overwrite new data.")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if args.restore:
        manifest = Path(args.restore)
        if not manifest.is_absolute():
            manifest = root / manifest
        try:
            restore_transaction(manifest)
        except (OSError, ValueError, json.JSONDecodeError, TransactionError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 80
        print(f"RESTORED_TRANSACTION={manifest.resolve()}")
        return 0

    plan_path = Path(args.plan)
    if not plan_path.is_absolute():
        plan_path = root / plan_path
    try:
        plan = load_plan(plan_path)
        actions, archive = build_actions(root, plan, args.archive_database)
    except (OSError, ValueError, json.JSONDecodeError, TransactionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 78

    if not actions:
        print("No existing rebuild evidence/database needs invalidation.")
        return 0

    mode = "APPLY" if args.apply else "DRY_RUN"
    print(f"REBUILD_INVALIDATION_MODE={mode}")
    for action in actions:
        print(f"{action['type'].upper()} {action['source']} -> {action['destination']}")

    if not args.apply:
        print("No files were moved. Re-run with --apply after reviewing the plan.")
        print("Applied transactions can later be restored with --restore <transaction.json> if no new data occupies the original paths.")
        return 0

    try:
        manifest = apply_transaction(
            root,
            actions,
            metadata={
                "source_plan": str(plan_path.resolve()),
                "earliest_rebuild_stage": plan.get("earliest_rebuild_stage"),
                "execution_targets": plan.get("execution_targets", []),
                "archive_root": str(archive),
                "pid": os.getpid(),
            },
        )
    except TransactionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 79

    print(f"INVALIDATION_ARCHIVE={archive}")
    print(f"TRANSACTION_MANIFEST={manifest}")
    print("TRANSACTION_STATE=APPLIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
