#!/usr/bin/env python3
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SPEC = importlib.util.spec_from_file_location("stage_metrics", ROOT / "python" / "build_stage_metrics.py")
metrics = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(metrics)
MOCK_SPEC = importlib.util.spec_from_file_location("mock_flow", ROOT / "python" / "run_mock_flow.py")
mock = importlib.util.module_from_spec(MOCK_SPEC); MOCK_SPEC.loader.exec_module(mock)


class StageMetricsTests(unittest.TestCase):
    def find(self, payload, name, source_contains=""):
        rows = [x for x in payload["metrics"] if x["metric"] == name and source_contains in x["source"]]
        self.assertTrue(rows, f"missing metric {name} source~{source_contains}")
        return rows[0]

    def test_mock_flow_generates_normalized_metrics_without_signoff_claim(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mock.generate_mock_run(root, "clean")
            synthesis = metrics.build_stage(root, "synthesis")
            self.assertEqual(synthesis["classification"], "MOCK")
            self.assertFalse(synthesis["signoff_qualified"])
            self.assertEqual(synthesis["mock_scenario"], "clean")
            self.assertAlmostEqual(self.find(synthesis, "setup_wns_ns")["value"], 0.35)
            self.assertAlmostEqual(self.find(synthesis, "total_cell_area_um2")["value"], 12345.0)
            self.assertAlmostEqual(self.find(synthesis, "total_w")["value"], 0.0095)
            self.assertTrue(all(row["classification"] == "MOCK" for row in synthesis["metrics"]))
            self.assertTrue(all(row["analysis_classification"] == "MOCK" for row in synthesis["metrics"]))

    def test_missing_reports_are_not_fabricated(self):
        with tempfile.TemporaryDirectory() as td:
            payload = metrics.build_stage(Path(td), "cts")
            self.assertEqual(payload["metrics"], [])
            self.assertTrue(payload["sources"])
            self.assertTrue(all(x["parse_status"] == "NOT_RUN" for x in payload["sources"]))

    def test_timing_failure_stays_mock_and_numeric(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); mock.generate_mock_run(root, "timing_fail")
            signoff = metrics.build_stage(root, "signoff")
            row = self.find(signoff, "setup_wns_ns", "summary.rpt")
            self.assertAlmostEqual(row["value"], -0.12)
            self.assertEqual(row["classification"], "MOCK")
            self.assertEqual(row["analysis_classification"], "MOCK")

    def test_all_metrics_is_stage_keyed_and_counted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); mock.generate_mock_run(root, "clean")
            payload = metrics.build_all(root, ["synthesis", "placement", "signoff"])
            self.assertEqual(set(payload["stages"]), {"synthesis", "placement", "signoff"})
            expected = sum(len(x["metrics"]) for x in payload["stages"].values())
            self.assertEqual(payload["metric_count"], expected)
            self.assertGreater(expected, 0)

    def test_multi_scenario_rows_preserve_context(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = root / "reports" / "signoff" / "summary.rpt"; report.parent.mkdir(parents=True)
            report.write_text((ROOT / "tests" / "fixtures" / "qor" / "timing_multi_scenario.rpt").read_text(), encoding="utf-8")
            payload = metrics.build_stage(root, "signoff")
            scenarios = {x["scenario"] for x in payload["metrics"] if x["metric"] == "setup_wns_ns" and x["scenario"]}
            self.assertEqual(scenarios, {"FUNC_SS", "FUNC_FF"})


if __name__ == "__main__": unittest.main()
