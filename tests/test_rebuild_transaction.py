import importlib.util
import json
import shutil
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rebuild_transaction", ROOT / "python" / "rebuild_transaction.py")
tx = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tx)


class RebuildTransactionTests(unittest.TestCase):
    def action(self, root: Path, name: str, kind: str = "evidence"):
        src = root / "checkpoints" / f"{name}.status"
        dst = root / "checkpoints" / "stale_archive" / f"{name}.status"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(f"stage={name}\nstatus=PASS\n", encoding="utf-8")
        return {"type": kind, "stage": name, "source": str(src), "destination": str(dst)}

    def test_apply_then_restore_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            action = self.action(root, "synthesis")
            original = Path(action["source"]).read_bytes()
            manifest = tx.apply_transaction(root, [action], metadata={"reason": "test"})
            data = json.loads(manifest.read_text())
            self.assertEqual(data["state"], "APPLIED")
            self.assertFalse(Path(action["source"]).exists())
            self.assertTrue(Path(action["destination"]).is_file())
            self.assertEqual(data["actions"][0]["pre_identity"]["sha256"], data["actions"][0]["post_identity"]["sha256"])

            tx.restore_transaction(manifest)
            data = json.loads(manifest.read_text())
            self.assertEqual(data["state"], "RESTORED")
            self.assertEqual(Path(action["source"]).read_bytes(), original)
            self.assertFalse(Path(action["destination"]).exists())

    def test_mid_transaction_failure_rolls_back_completed_moves(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = self.action(root, "a")
            second = self.action(root, "b")
            calls = {"count": 0}

            def fail_second(src, dst):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise OSError("simulated move failure")
                return shutil.move(src, dst)

            with self.assertRaises(tx.TransactionError) as ctx:
                tx.apply_transaction(root, [first, second], move_func=fail_second)
            self.assertIn("ROLLED_BACK", str(ctx.exception))
            self.assertTrue(Path(first["source"]).is_file())
            self.assertTrue(Path(second["source"]).is_file())
            self.assertFalse(Path(first["destination"]).exists())

            manifests = list((root / "checkpoints" / "rebuild_transactions").glob("*/transaction.json"))
            self.assertEqual(len(manifests), 1)
            self.assertEqual(json.loads(manifests[0].read_text())["state"], "ROLLED_BACK")

    def test_database_move_creates_placeholder_and_restore_removes_it(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            database = root / "database"
            (database / "MIPS_16.dlib").mkdir(parents=True)
            (database / "MIPS_16.dlib" / "block.ndm").write_bytes(b"database")
            archive = root / "runs" / "stale_database_archive" / "run1" / "database"
            action = {"type": "database", "stage": "icc2_init", "source": str(database), "destination": str(archive)}

            manifest = tx.apply_transaction(root, [action])
            self.assertTrue(database.is_dir())
            self.assertEqual(list(database.iterdir()), [])
            self.assertTrue((archive / "MIPS_16.dlib" / "block.ndm").is_file())

            tx.restore_transaction(manifest)
            self.assertEqual((database / "MIPS_16.dlib" / "block.ndm").read_bytes(), b"database")
            self.assertFalse(archive.exists())

    def test_restore_refuses_to_overwrite_new_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            action = self.action(root, "route")
            manifest = tx.apply_transaction(root, [action])
            Path(action["source"]).parent.mkdir(parents=True, exist_ok=True)
            Path(action["source"]).write_text("new route evidence\n", encoding="utf-8")
            with self.assertRaises(tx.TransactionError):
                tx.restore_transaction(manifest)
            self.assertEqual(json.loads(manifest.read_text())["state"], "APPLIED")
            self.assertEqual(Path(action["source"]).read_text(), "new route evidence\n")
            self.assertTrue(Path(action["destination"]).exists())

    def test_preflight_rejects_missing_source_before_any_move(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = self.action(root, "a")
            missing = {
                "type": "evidence",
                "stage": "b",
                "source": str(root / "checkpoints" / "missing.status"),
                "destination": str(root / "checkpoints" / "stale_archive" / "missing.status"),
            }
            with self.assertRaises(tx.TransactionError):
                tx.apply_transaction(root, [first, missing])
            self.assertTrue(Path(first["source"]).exists())
            self.assertFalse(Path(first["destination"]).exists())


if __name__ == "__main__":
    unittest.main()
