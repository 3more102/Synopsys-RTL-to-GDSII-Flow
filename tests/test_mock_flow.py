import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


mock = load_module("run_mock_flow", "python/run_mock_flow.py")
validator = load_module("validate_mock_flow", "python/validate_mock_flow.py")
triage = load_module("triage_failure_for_mock", "python/triage_failure.py")
stage_metrics = load_module("stage_metrics_for_mock", "python/build_stage_metrics.py")
metric_regression = load_module("metric_regression_for_mock", "python/check_metric_regression.py")


class MockFlowTests(unittest.TestCase):
    def run_scenario(self, scenario):
        td = tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        root = Path(td.name) / "run"; mock.generate_mock_run(root, scenario, "MOCK_CHIP")
        result = validator.validate_mock_run(root); return root, result

    def test_clean_scenario_parses_and_remains_mock_only(self):
        root, result = self.run_scenario("clean")
        self.assertEqual(result["status"], "PASS"); self.assertTrue(result["mock"]); self.assertFalse(result["signoff_qualified"])
        self.assertGreaterEqual(result["metrics"]["signoff_wns"], 0); self.assertEqual(result["metrics"]["drc"], 0)
        self.assertAlmostEqual(result["metrics"]["clock_skew"], 0.041); self.assertEqual(result["metrics"]["via_count"], 91234)
        status = (root / "reports/status/setup_sta.status").read_text(); self.assertIn("status=MOCK_PASS", status); self.assertNotIn("status=PASS", status)
        self.assertIn(mock.MOCK_HEADER, (root / "gds/MOCK_CHIP.gds").read_text())

    def test_timing_failure_is_proven_by_real_parser(self):
        _, result = self.run_scenario("timing_fail")
        self.assertEqual(result["status"], "PASS"); self.assertLess(result["metrics"]["signoff_wns"], 0); self.assertGreater(result["metrics"]["setup_violations"], 0)

    def test_hold_failure_is_proven_by_real_parser(self):
        root, result = self.run_scenario("hold_fail")
        self.assertEqual(result["status"], "PASS"); self.assertLess(result["metrics"]["hold_slack"], 0); self.assertGreater(result["metrics"]["hold_violations"], 0)
        self.assertIn("status=MOCK_FAIL", (root / "reports/status/hold_sta.status").read_text())

    def test_multi_corner_preserves_two_contexts(self):
        root, result = self.run_scenario("multi_corner")
        self.assertEqual(result["status"], "PASS"); self.assertLess(result["metrics"]["signoff_wns"], 0)
        payload = stage_metrics.build_stage(root, "signoff")
        rows = [r for r in payload["metrics"] if r["metric"] == "setup_wns_ns" and r["scenario"]]
        self.assertEqual({r["scenario"] for r in rows}, {"FUNC_SS_MOCK", "FUNC_FF_MOCK"})
        self.assertEqual({r["corner"] for r in rows}, {"SS_MOCK", "FF_MOCK"})

    def test_drc_failure_is_proven_by_real_parser(self):
        _, result = self.run_scenario("drc_fail")
        self.assertEqual(result["status"], "PASS"); self.assertGreater(result["metrics"]["drc"], 0)

    def test_qor_regression_scenario_exercises_normalized_gate(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            baseline_root = Path(a) / "run"; current_root = Path(b) / "run"
            mock.generate_mock_run(baseline_root, "clean", "MOCK_CHIP"); mock.generate_mock_run(current_root, "qor_regression", "MOCK_CHIP")
            self.assertEqual(validator.validate_mock_run(current_root)["status"], "PASS")
            baseline = stage_metrics.build_all(baseline_root, ["synthesis", "placement", "cts", "route", "signoff"])
            current = stage_metrics.build_all(current_root, ["synthesis", "placement", "cts", "route", "signoff"])
            policy = json.loads((ROOT / "config/metric_regression_policy.json").read_text())
            result = metric_regression.compare(current, baseline, policy)
            self.assertEqual(result["status"], "WARN")
            warned = {row["metric"] for row in result["checks"] if row["status"] == "WARN"}
            self.assertTrue({"total_cell_area_um2", "total_w"} & warned)
            self.assertTrue(all(row["classification"] == "MOCK" for row in result["checks"]))

    def test_missing_artifact_is_intentional_and_labeled(self):
        root, result = self.run_scenario("missing_artifact")
        self.assertEqual(result["status"], "PASS"); self.assertFalse((root / "spef/MOCK_CHIP_postroute.spef").exists())
        self.assertIn("status=MOCK_FAIL", (root / "reports/status/extraction.status").read_text())

    def test_license_failure_exercises_existing_triage_signatures(self):
        root, result = self.run_scenario("license_fail")
        self.assertEqual(result["status"], "PASS")
        signatures = triage.load_signatures(ROOT / "config/failure_signatures.json")
        findings = triage.classify((root / "logs/10_synthesis_mock.log").read_text(), signatures)
        self.assertTrue(findings); self.assertEqual(findings[0]["category"], "license")

    def test_report_and_artifact_payloads_are_deterministic(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            ra = Path(a) / "run"; rb = Path(b) / "run"; mock.generate_mock_run(ra, "clean", "MOCK_CHIP"); mock.generate_mock_run(rb, "clean", "MOCK_CHIP")
            comparable = ["reports/synthesis/qor.rpt", "reports/synthesis/area.rpt", "reports/synthesis/power.rpt", "reports/cts/post_cts_clock_timing.rpt", "reports/signoff/summary.rpt", "reports/signoff/setup.rpt", "reports/route/route_status.rpt", "netlist/MOCK_CHIP_postroute.v", "spef/MOCK_CHIP_postroute.spef", "sdf/MOCK_CHIP_postroute.sdf", "gds/MOCK_CHIP.gds"]
            for rel in comparable: self.assertEqual((ra / rel).read_bytes(), (rb / rel).read_bytes(), rel)

    def test_force_refuses_non_mock_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "run"; root.mkdir(); (root / "user_file.txt").write_text("do not delete")
            with self.assertRaises(ValueError): mock.generate_mock_run(root, "clean", "MOCK_CHIP", force=True)
            self.assertEqual((root / "user_file.txt").read_text(), "do not delete")


if __name__ == "__main__": unittest.main()
