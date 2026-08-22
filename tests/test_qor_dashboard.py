#!/usr/bin/env python3
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("qor_dashboard", ROOT / "python" / "qor_dashboard.py")
dash = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(dash)
METRIC_SPEC = importlib.util.spec_from_file_location("stage_metrics", ROOT / "python" / "build_stage_metrics.py")
metric_builder = importlib.util.module_from_spec(METRIC_SPEC); METRIC_SPEC.loader.exec_module(metric_builder)
MOCK_SPEC = importlib.util.spec_from_file_location("mock_flow", ROOT / "python" / "run_mock_flow.py")
mock = importlib.util.module_from_spec(MOCK_SPEC); MOCK_SPEC.loader.exec_module(mock)


class QorDashboardTests(unittest.TestCase):
    def test_mock_dashboard_is_labeled_and_uses_available_metrics_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); mock.generate_mock_run(root, "clean")
            payload = metric_builder.build_all(root, ["synthesis", "placement", "signoff"])
            metrics = root / "metrics.json"; metrics.write_text(json.dumps(payload), encoding="utf-8")
            reg = root / "reg.json"; reg.write_text(json.dumps({"status": "PASS", "baseline": "mock-baseline"}), encoding="utf-8")
            out = root / "dashboard"; rows, meta = dash.generate(metrics, reg, out)
            self.assertEqual(meta["classification"], "MOCK")
            self.assertFalse(meta["signoff_qualified"])
            self.assertEqual(meta["regression"], "PASS")
            self.assertGreaterEqual(len(rows), 2)
            text = (out / "qor_dashboard.txt").read_text()
            self.assertIn("Classification: MOCK", text)
            self.assertIn("Parsed metrics are evidence only", text)
            self.assertNotIn("None ns", text)
            for name in ("qor_dashboard.txt", "qor_dashboard.md", "qor_dashboard.html"):
                self.assertTrue((out / name).is_file())

    def test_metric_formatting_normalizes_display_units(self):
        self.assertEqual(dash.fmt_metric({"value": 0.0187, "unit": "W"}), "18.7 mW")
        self.assertEqual(dash.fmt_metric({"value": 1_218_000.0, "unit": "um^2"}), "1.218 mm²")
        self.assertEqual(dash.fmt_metric({"value": 0.684, "unit": "ratio"}), "68.4%")
        self.assertEqual(dash.fmt_metric({"value": 1425000.0, "unit": "um"}), "1425 mm")

    def test_empty_metrics_generate_safe_empty_dashboard(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); metrics = root / "metrics.json"; metrics.write_text(json.dumps({"classification": "REAL", "run": {}, "stages": {}}))
            out = root / "out"; rows, meta = dash.generate(metrics, root / "missing.json", out)
            self.assertEqual(rows, [])
            self.assertEqual(meta["regression"], "NO_BASELINE")
            self.assertIn("No normalized metrics available", (out / "qor_dashboard.html").read_text())

    def test_summary_prefers_summary_report_for_setup_metric(self):
        stage = {
            "metrics": [
                {"metric": "setup_wns_ns", "value": 0.2, "unit": "ns", "parse_status": "PARSED", "source": "reports/signoff/setup.rpt"},
                {"metric": "setup_wns_ns", "value": 0.1, "unit": "ns", "parse_status": "PARSED", "source": "reports/signoff/summary.rpt"},
            ]
        }
        self.assertEqual(dash.numeric_metric(stage, "setup_wns_ns")["value"], 0.1)


if __name__ == "__main__": unittest.main()
