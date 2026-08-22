import importlib.util
import json
import os
import socket
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("stage_locks", ROOT / "python" / "stage_locks.py")
locks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(locks)


class StageLockTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root = Path(self.td.name).resolve()
        self.old_root = locks.ROOT
        self.old_lock_root = locks.DEFAULT_LOCK_ROOT
        self.old_archive_root = locks.DEFAULT_ARCHIVE_ROOT
        locks.ROOT = self.root
        locks.DEFAULT_LOCK_ROOT = self.root / "work" / "locks"
        locks.DEFAULT_ARCHIVE_ROOT = self.root / "work" / "stale_locks"
        locks.DEFAULT_LOCK_ROOT.mkdir(parents=True)
        self.addCleanup(self.restore_globals)

    def restore_globals(self):
        locks.ROOT = self.old_root
        locks.DEFAULT_LOCK_ROOT = self.old_lock_root
        locks.DEFAULT_ARCHIVE_ROOT = self.old_archive_root

    def lock_dir(self, name="synthesis"):
        path = locks.DEFAULT_LOCK_ROOT / f"{name}.lock"
        path.mkdir(parents=True)
        return path

    def write_owner(self, lock_dir, **updates):
        owner = locks.owner_record(
            "synthesis",
            "dc_shell",
            "scripts/synthesis/01_synthesis.tcl",
            "run-001",
            pid=os.getpid(),
            ppid=os.getppid(),
        )
        owner.update(updates)
        (lock_dir / locks.OWNER_FILE).write_text(json.dumps(owner), encoding="utf-8")
        return owner

    def test_recorded_runner_pid_is_active_not_helper_pid(self):
        lock_dir = self.lock_dir()
        owner_path = locks.write_owner(
            lock_dir,
            "synthesis",
            "dc_shell",
            "scripts/synthesis/01_synthesis.tcl",
            "run-001",
            pid=os.getpid(),
            ppid=os.getppid(),
        )
        owner = json.loads(owner_path.read_text())
        self.assertEqual(owner["pid"], os.getpid())
        self.assertEqual(locks.inspect_lock(lock_dir)["state"], "ACTIVE")

    def test_dead_same_host_pid_is_stale(self):
        lock_dir = self.lock_dir()
        self.write_owner(lock_dir, pid=99999999, process_start_ticks="")
        info = locks.inspect_lock(lock_dir)
        self.assertEqual(info["state"], "STALE")
        self.assertIn("not alive", info["reason"])

    def test_foreign_host_is_never_auto_classified_stale(self):
        lock_dir = self.lock_dir()
        self.write_owner(lock_dir, hostname="foreign-host.invalid")
        info = locks.inspect_lock(lock_dir)
        self.assertEqual(info["state"], "FOREIGN_HOST")
        with self.assertRaises(RuntimeError):
            locks.recover_stale(lock_dir, locks.DEFAULT_ARCHIVE_ROOT)
        self.assertTrue(lock_dir.exists())

    def test_missing_owner_is_unknown(self):
        lock_dir = self.lock_dir()
        info = locks.inspect_lock(lock_dir)
        self.assertEqual(info["state"], "UNKNOWN")
        self.assertIn("owner.json missing", info["reason"])

    def test_boot_change_proves_same_host_lock_stale(self):
        lock_dir = self.lock_dir()
        if not locks.boot_id():
            self.skipTest("boot identity unavailable on this platform")
        self.write_owner(lock_dir, boot_id="different-boot-id")
        info = locks.inspect_lock(lock_dir)
        self.assertEqual(info["state"], "STALE")
        self.assertIn("boot identity changed", info["reason"])

    def test_pid_reuse_identity_mismatch_is_stale(self):
        lock_dir = self.lock_dir()
        if not locks.process_start_ticks(os.getpid()):
            self.skipTest("process start identity unavailable on this platform")
        self.write_owner(lock_dir, process_start_ticks="definitely-not-current-start")
        info = locks.inspect_lock(lock_dir)
        self.assertEqual(info["state"], "STALE")
        self.assertIn("reused", info["reason"])

    def test_recovery_archives_stale_lock_instead_of_deleting(self):
        lock_dir = self.lock_dir()
        self.write_owner(lock_dir, pid=99999999, process_start_ticks="")
        archive = locks.recover_stale(lock_dir, locks.DEFAULT_ARCHIVE_ROOT)
        self.assertFalse(lock_dir.exists())
        self.assertTrue((archive / locks.OWNER_FILE).is_file())
        recovery = json.loads((archive / "recovery.json").read_text())
        self.assertEqual(recovery["recovery"], "archived_not_deleted")
        self.assertEqual(recovery["inspection"]["state"], "STALE")

    def test_active_lock_cannot_be_recovered(self):
        lock_dir = self.lock_dir()
        self.write_owner(lock_dir)
        with self.assertRaises(RuntimeError):
            locks.recover_stale(lock_dir, locks.DEFAULT_ARCHIVE_ROOT)
        self.assertTrue(lock_dir.exists())


if __name__ == "__main__":
    unittest.main()
