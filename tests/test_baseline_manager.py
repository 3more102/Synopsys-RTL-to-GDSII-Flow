import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("manage_baseline", ROOT / "python" / "manage_baseline.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class BaselineManagerTests(unittest.TestCase):
    def make_source(self, root: Path, status: str = "PASS") -> None:
        (root / "reports" / "summary").mkdir(parents=True)
        (root / "reports" / "provenance").mkdir(parents=True)
        (root / "reports" / "summary" / "qor_summary.json").write_text(json.dumps([{"Stage": "Signoff", "WNS": 0.1}]), encoding="utf-8")
        (root / "reports" / "provenance" / "run_provenance.json").write_text(json.dumps({"provenance_digest": "digest", "git": {"commit": "abc"}}), encoding="utf-8")
        (root / "reports" / "summary" / "release_verification.json").write_text(json.dumps({"status": status}), encoding="utf-8")

    def test_verified_current_run_promotes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_source(root, "PASS")
            out = mod.promote(root, root / "baselines" / "local", "golden", "current", False, False)
            self.assertTrue((out / "qor_summary.json").is_file())
            ok, errors = mod.verify_baseline(out)
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_unverified_run_is_rejected_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_source(root, "UNKNOWN")
            with self.assertRaises(ValueError):
                mod.promote(root, root / "baselines" / "local", "candidate", "current", False, False)

    def test_unverified_run_can_be_explicitly_provisional(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_source(root, "UNKNOWN")
            out = mod.promote(root, root / "baselines" / "local", "candidate", "current", True, False)
            metadata = json.loads((out / "BASELINE.json").read_text())
        self.assertTrue(metadata["provisional"])
        self.assertEqual(metadata["release_status"], "UNKNOWN")

    def test_tampered_baseline_fails_integrity(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_source(root, "PASS")
            out = mod.promote(root, root / "baselines" / "local", "golden", "current", False, False)
            (out / "qor_summary.json").write_text("[]", encoding="utf-8")
            ok, errors = mod.verify_baseline(out)
        self.assertFalse(ok)
        self.assertTrue(any("mismatch" in e for e in errors))

    def test_replace_archives_old_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_source(root, "PASS")
            baseline_root = root / "baselines" / "local"
            first = mod.promote(root, baseline_root, "golden", "current", False, False)
            (first / "marker.txt").write_text("old", encoding="utf-8")
            second = mod.promote(root, baseline_root, "golden", "current", False, True)
            archives = list((baseline_root / ".archive").glob("*_golden"))
            self.assertTrue(second.is_dir())
            self.assertEqual(len(archives), 1)
            self.assertTrue((archives[0] / "marker.txt").is_file())


if __name__ == "__main__":
    unittest.main()
