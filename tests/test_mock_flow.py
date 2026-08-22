import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mock = load_module("run_mock_flow", "python/run_mock_flow.py")
validator = load_module("validate_mock_flow", "python/validate_mock_flow.py")
triage = load_module("triage_failure_for_mock", "python/triage_failure.py")


class MockFlowTests(unittest.TestCase):
    def run_scenario(self, scenario):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name) / "run"
        mock.generate_mock_run(root, scenario, "MOCK_CHIP")
        result = validator.validate_mock_run(root)
        return root, result

    def test_clean_scenario_parses_and_remains_mock_only(self):
        root, result = self.run_scenario("clean")
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["mock"])
        self.assertFalse(result["signoff_qualified"])
        self.assertGreaterEqual(result["metrics"]["signoff_wns"], 0)
        self.assertEqual(result["metrics"]["drc"], 0)
        status = (root / "reports/status/setup_sta.status").read_text()
        self.assertIn("status=MOCK_PASS", status)
        self.assertNotIn("status=PASS", status)
        self.assertIn(mock.MOCK_HEADER, (root / "gds/MOCK_CHIP.gds").read_text())

    def test_timing_failure_is_proven_by_real_parser(self):
        _, result = self.run_scenario("timing_fail")
        self.assertEqual(result["status"], "PASS")
        self.assertLess(result["metrics"]["signoff_wns"], 0)
        self.assertGreater(result["metrics"]["setup_violations"], 0)

    def test_drc_failure_is_proven_by_real_parser(self):
        _, result = self.run_scenario("drc_fail")
        self.assertEqual(result["status"], "PASS")
        self.assertGreater(result["metrics"]["drc"], 0)

    def test_missing_artifact_is_intentional_and_labeled(self):
        root, result = self.run_scenario("missing_artifact")
        self.assertEqual(result["status"], "PASS")
        self.assertFalse((root / "spef/MOCK_CHIP_postroute.spef").exists())
        self.assertIn("status=MOCK_FAIL", (root / "reports/status/extraction.status").read_text())

    def test_license_failure_exercises_existing_triage_signatures(self):
        root, result = self.run_scenario("license_fail")
        self.assertEqual(result["status"], "PASS")
        signatures = triage.load_signatures(ROOT / "config/failure_signatures.json")
        findings = triage.classify((root / "logs/10_synthesis_mock.log").read_text(), signatures)
        self.assertTrue(findings)
        self.assertEqual(findings[0]["category"], "license")

    def test_report_and_artifact_payloads_are_deterministic(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            ra = Path(a) / "run"
            rb = Path(b) / "run"
            mock.generate_mock_run(ra, "clean", "MOCK_CHIP")
            mock.generate_mock_run(rb, "clean", "MOCK_CHIP")
            comparable = [
                "reports/synthesis/qor.rpt",
                "reports/synthesis/area.rpt",
                "reports/signoff/summary.rpt",
                "reports/signoff/setup.rpt",
                "reports/route/route_status.rpt",
                "netlist/MOCK_CHIP_postroute.v",
                "spef/MOCK_CHIP_postroute.spef",
                "sdf/MOCK_CHIP_postroute.sdf",
                "gds/MOCK_CHIP.gds",
            ]
            for rel in comparable:
                self.assertEqual((ra / rel).read_bytes(), (rb / rel).read_bytes(), rel)

    def test_force_refuses_non_mock_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "run"
            root.mkdir()
            (root / "user_file.txt").write_text("do not delete")
            with self.assertRaises(ValueError):
                mock.generate_mock_run(root, "clean", "MOCK_CHIP", force=True)
            self.assertEqual((root / "user_file.txt").read_text(), "do not delete")


if __name__ == "__main__":
    unittest.main()
