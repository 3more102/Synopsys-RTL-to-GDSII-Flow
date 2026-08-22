import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("index_run_history", ROOT / "python" / "index_run_history.py")
hist = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hist)


class RunHistoryTests(unittest.TestCase):
    def make_run(self, root: Path, name: str, wns: float, area: float, runtime: float) -> Path:
        run = root / "runs" / name
        summary = run / "reports" / "summary"
        provenance = run / "reports" / "provenance"
        summary.mkdir(parents=True)
        provenance.mkdir(parents=True)
        rows = [
            {"Stage": "Post-Route", "WNS": wns, "TNS": -1.0, "Worst Hold Slack": 0.02, "Area": area, "Utilization": 65.0, "Cell Count": 1000, "Power": None, "Runtime": runtime},
            {"Stage": "Signoff", "WNS": wns + 0.01, "TNS": 0.0, "Worst Hold Slack": 0.03, "Area": None, "Utilization": None, "Cell Count": None, "Power": 0.5, "Runtime": runtime / 2},
        ]
        (summary / "qor_summary.json").write_text(json.dumps(rows), encoding="utf-8")
        (summary / "release_verification.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
        (provenance / "run_provenance.json").write_text(json.dumps({"provenance_digest": f"digest-{name}"}), encoding="utf-8")
        (run / "manifest.txt").write_text(f"date=2026-08-22T10:00:00+03:00\ngit_commit={name}\ngit_dirty=NO\n", encoding="utf-8")
        return run

    def test_summarize_uses_signoff_timing_and_postroute_area(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run = self.make_run(root, "run1", -0.10, 1234.0, 20.0)
            record = hist.summarize_run(run)
        self.assertEqual(record["WNS"], -0.09)
        self.assertEqual(record["Area"], 1234.0)
        self.assertEqual(record["Runtime"], 30.0)
        self.assertEqual(record["Release Status"], "PASS")

    def test_deltas_are_between_adjacent_runs(self):
        records = [{"WNS": -0.2, "Area": 100.0}, {"WNS": 0.1, "Area": 110.0}]
        hist.add_deltas(records)
        self.assertIsNone(records[0]["Delta"]["WNS"])
        self.assertAlmostEqual(records[1]["Delta"]["WNS"], 0.3)
        self.assertAlmostEqual(records[1]["Delta"]["Area"], 10.0)

    def test_write_outputs_creates_all_formats(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "history"
            records = [{"Run": "r", "Date": "", "Git Commit": "abc", "Provenance": "p", "Release Status": "PASS", "QoR Gate": "PASS", "WNS": 0.0, "TNS": 0.0, "Worst Hold Slack": 0.1, "Area": 10.0, "Utilization": 50.0, "Cell Count": 100, "Power": 0.2, "Runtime": 3.0, "Delta": {}}]
            hist.write_outputs(records, out)
            for name in ("run_history.json", "run_history.csv", "run_history.md", "run_history.html"):
                self.assertTrue((out / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
