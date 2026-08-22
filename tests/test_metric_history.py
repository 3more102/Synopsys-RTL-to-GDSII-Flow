#!/usr/bin/env python3
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("metric_history", ROOT / "python" / "index_metric_history.py")
hist = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(hist)


class MetricHistoryTests(unittest.TestCase):
    def payload(self, classification="REAL", run_id="run1"):
        return {
            "classification": classification,
            "run": {"project": "chip", "top": "top", "git_commit": "abc", "branch": "main", "provenance_digest": "prov"},
            "stages": {
                "signoff": {
                    "classification": classification,
                    "tool": "pt_shell" if classification == "REAL" else "mock_signoff",
                    "run": {"project": "chip", "top": "top", "git_commit": "abc", "branch": "main", "provenance_digest": "prov", "run_id": run_id},
                    "metrics": [
                        {"metric": "setup_wns_ns", "value": 0.05, "unit": "ns", "parse_status": "PARSED", "scenario": "FUNC_SS", "mode": "FUNC", "corner": "SS", "path_group": "REG2REG", "classification": classification, "analysis_classification": "SIGNOFF_CANDIDATE" if classification == "REAL" else "MOCK", "source": "reports/signoff/summary.rpt"},
                        {"metric": "total_w", "value": 0.01, "unit": "W", "parse_status": "PARSED", "scenario": "", "mode": "", "corner": "", "path_group": "", "classification": classification, "analysis_classification": "SIGNOFF_CANDIDATE" if classification == "REAL" else "MOCK", "source": "reports/power/vectorless_power.rpt"},
                    ],
                }
            },
        }

    def test_metric_rows_preserve_comparability_dimensions(self):
        rows = hist.metric_rows(self.payload(), "r1", "2026-08-22T10:00:00Z")
        self.assertEqual(len(rows), 2)
        timing = next(x for x in rows if x["metric"] == "setup_wns_ns")
        self.assertEqual(timing["scenario"], "FUNC_SS")
        self.assertEqual(timing["corner"], "SS")
        self.assertIn("signoff", timing["comparison_key"])
        self.assertIn("REAL", timing["comparison_key"])

    def test_mock_and_real_get_different_comparison_keys(self):
        real = hist.metric_rows(self.payload("REAL"), "r1")[0]
        mock = hist.metric_rows(self.payload("MOCK"), "r2")[0]
        self.assertNotEqual(real["comparison_key"], mock["comparison_key"])
        self.assertEqual(mock["classification"], "MOCK")

    def test_archived_run_without_metrics_is_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td) / "runs" / "r"; run.mkdir(parents=True)
            self.assertEqual(hist.rows_from_run(run), [])

    def test_build_and_write_history(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); run = root / "runs" / "20260822_r1"; path = run / "reports" / "metrics"; path.mkdir(parents=True)
            (path / "all_metrics.json").write_text(json.dumps(self.payload()), encoding="utf-8")
            (run / "manifest.txt").write_text("date=2026-08-22T10:00:00Z\n", encoding="utf-8")
            rows = hist.build_history(root / "runs")
            self.assertEqual(len(rows), 2)
            out = root / "history"; hist.write_outputs(rows, out)
            for name in ("metric_history.json", "metric_history.jsonl", "metric_history.csv"):
                self.assertTrue((out / name).is_file())
            jsonl = (out / "metric_history.jsonl").read_text().strip().splitlines()
            self.assertEqual(len(jsonl), 2)


if __name__ == "__main__": unittest.main()
