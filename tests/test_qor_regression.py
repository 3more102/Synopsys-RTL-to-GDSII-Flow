#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from check_qor_regression import evaluate_metric, run


class QorRegressionTests(unittest.TestCase):
    def test_signoff_absolute_min_failure(self):
        r = evaluate_metric('Signoff', 'WNS', 0.10, -0.01, {'direction': 'higher', 'absolute_min': 0.0, 'max_regression_abs': 0.0, 'severity': 'fail', 'require_current': True, 'require_baseline': True})
        self.assertEqual(r['status'], 'FAIL')

    def test_no_timing_regression_passes(self):
        r = evaluate_metric('Signoff', 'WNS', 0.10, 0.12, {'direction': 'higher', 'absolute_min': 0.0, 'max_regression_abs': 0.0, 'severity': 'fail', 'require_current': True, 'require_baseline': True})
        self.assertEqual(r['status'], 'PASS')

    def test_optional_missing_metric_skips(self):
        r = evaluate_metric('Synthesis', 'Power', None, None, {'direction': 'lower', 'max_regression_percent': 5.0, 'severity': 'warn', 'require_current': False})
        self.assertEqual(r['status'], 'SKIP')

    def test_warning_does_not_fail_gate(self):
        policy = {'stages': {'Synthesis': {'Area': {'direction': 'lower', 'max_regression_percent': 5.0, 'severity': 'warn'}}}}
        results, failures, warnings = run(policy, {'Synthesis': {'Area': 100.0}}, {'Synthesis': {'Area': 110.0}})
        self.assertEqual(len(failures), 0)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(results[0]['status'], 'WARN')

    def test_required_baseline_missing_fails(self):
        r = evaluate_metric('Signoff', 'TNS', None, 0.0, {'direction': 'higher', 'absolute_min': 0.0, 'max_regression_abs': 0.0, 'severity': 'fail', 'require_current': True, 'require_baseline': True})
        self.assertEqual(r['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
