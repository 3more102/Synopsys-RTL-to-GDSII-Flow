#!/usr/bin/env python3
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("metric_regression", ROOT / "python" / "check_metric_regression.py")
reg = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(reg)


class MetricRegressionTests(unittest.TestCase):
    def payload(self, value, metric="setup_wns_ns", *, stage="signoff", classification="REAL", source="reports/signoff/summary.rpt", scenario="FUNC_SS", corner="SS", unit="ns"):
        return {
            "run": {"project": "chip", "top": "top", "provenance_digest": "p"},
            "stages": {
                stage: {
                    "run": {"project": "chip", "top": "top", "provenance_digest": "p"},
                    "metrics": [{
                        "metric": metric, "value": value, "unit": unit, "parse_status": "PARSED",
                        "scenario": scenario, "mode": "FUNC", "corner": corner, "path_group": "REG2REG",
                        "classification": classification,
                        "analysis_classification": "MOCK" if classification == "MOCK" else ("SIGNOFF_CANDIDATE" if stage == "signoff" else "IMPLEMENTATION"),
                        "source": source,
                    }],
                }
            },
        }

    def policy(self, metric="setup_wns_ns", **rule):
        base = {"direction": "higher", "max_regression_abs": 0.05, "severity": "fail"}
        base.update(rule)
        return {"schema_version": 1, "metrics": {metric: base}}

    def test_wns_regression_fails_with_correct_direction(self):
        baseline = self.payload(0.10)
        current = self.payload(0.02)
        result = reg.compare(current, baseline, self.policy())
        self.assertEqual(result["status"], "FAIL")
        self.assertAlmostEqual(result["checks"][0]["regression"], 0.08)

    def test_area_small_regression_passes_and_large_warns(self):
        policy = self.policy("total_cell_area_um2", direction="lower", max_regression_percent=2.0, severity="warn")
        baseline = self.payload(100.0, "total_cell_area_um2", stage="placement", source="reports/placement/utilization.rpt", scenario="", corner="", unit="um^2")
        small = self.payload(101.0, "total_cell_area_um2", stage="placement", source="reports/placement/utilization.rpt", scenario="", corner="", unit="um^2")
        large = self.payload(103.0, "total_cell_area_um2", stage="placement", source="reports/placement/utilization.rpt", scenario="", corner="", unit="um^2")
        self.assertEqual(reg.compare(small, baseline, policy)["status"], "PASS")
        self.assertEqual(reg.compare(large, baseline, policy)["status"], "WARN")

    def test_mock_never_compares_to_real(self):
        baseline = self.payload(0.10, classification="REAL")
        current = self.payload(0.10, classification="MOCK")
        result = reg.compare(current, baseline, self.policy())
        self.assertEqual(result["status"], "NOT_COMPARABLE")
        self.assertEqual(result["not_comparable_count"], 1)

    def test_stage_mismatch_is_not_comparable(self):
        baseline = self.payload(0.10, stage="signoff")
        current = self.payload(0.10, stage="synthesis", source="reports/synthesis/qor.rpt")
        result = reg.compare(current, baseline, self.policy())
        self.assertEqual(result["status"], "NOT_COMPARABLE")

    def test_corner_mismatch_is_not_comparable(self):
        baseline = self.payload(0.10, corner="SS")
        current = self.payload(0.10, corner="FF")
        self.assertEqual(reg.compare(current, baseline, self.policy())["status"], "NOT_COMPARABLE")

    def test_missing_baseline_is_explicit(self):
        self.assertEqual(reg.compare(self.payload(0.1), None, self.policy())["status"], "NO_BASELINE")

    def test_zero_baseline_percentage_has_defined_failure_semantics(self):
        policy = self.policy("total_w", direction="lower", max_regression_percent=3.0, severity="warn")
        baseline = self.payload(0.0, "total_w", source="reports/power/vectorless_power.rpt", scenario="", corner="", unit="W")
        current = self.payload(0.1, "total_w", source="reports/power/vectorless_power.rpt", scenario="", corner="", unit="W")
        result = reg.compare(current, baseline, policy)
        self.assertEqual(result["status"], "WARN")
        self.assertIn("baseline is zero", result["checks"][0]["messages"][0])

    def test_duplicate_baseline_identity_is_not_comparable(self):
        baseline = self.payload(0.10)
        row = dict(baseline["stages"]["signoff"]["metrics"][0])
        baseline["stages"]["signoff"]["metrics"].append(row)
        result = reg.compare(self.payload(0.09), baseline, self.policy())
        self.assertEqual(result["status"], "NOT_COMPARABLE")
        self.assertIn("duplicate", result["checks"][0]["messages"][0])

    def test_non_numeric_current_is_not_comparable(self):
        result = reg.compare(self.payload(None), self.payload(0.1), self.policy())
        self.assertEqual(result["status"], "NOT_COMPARABLE")

    def test_invalid_direction_fails_policy_evaluation(self):
        status, _, _, messages = reg.evaluate_rule(1.0, 1.0, {"direction": "sideways"})
        self.assertEqual(status, "FAIL")
        self.assertIn("invalid direction", messages[0])


if __name__ == "__main__": unittest.main()
