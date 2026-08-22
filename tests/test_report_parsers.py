#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))

from qor_parsers import parse_area_util, parse_congestion, parse_drc, parse_power, parse_qor
from report_utils import latest_runtime, slack_from_timing, violated_path_count


class QorParserTests(unittest.TestCase):
    def test_qor_metrics(self):
        sample = 'WNS : -0.125\nTNS : -2.75\nNo. of Violating Paths : 14\n'
        self.assertEqual(parse_qor(sample), (-0.125, -2.75, 14))

    def test_area_utilization_and_cells_are_independent(self):
        sample = 'Total cell area: 1234.50\nUtilization Ratio: 0.67\nNumber of cells: 842\n'
        self.assertEqual(parse_area_util(sample), (1234.5, 0.67, 842))

    def test_power_congestion_and_drc(self):
        self.assertEqual(parse_power('Total Power = 1.25e-03'), 1.25e-3)
        self.assertEqual(parse_congestion('Total Overflow : 3.4'), 3.4)
        self.assertEqual(parse_drc('Total number of violations = 7'), 7)

    def test_missing_metric_is_none(self):
        self.assertEqual(parse_qor('no timing summary here'), (None, None, None))
        self.assertIsNone(parse_power('power report unavailable'))

    def test_hold_path_detection(self):
        sample = 'slack (VIOLATED) -0.04\nslack (MET) 0.10\nslack (VIOLATED) -0.01\n'
        self.assertEqual(slack_from_timing(sample), -0.04)
        self.assertEqual(violated_path_count(sample), 2)

    def test_runtime_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'reports' / 'runtime'
            p.mkdir(parents=True)
            (p / 'route.latest.json').write_text(json.dumps({'duration_seconds': 37}))
            self.assertEqual(latest_runtime(Path(td), 'route'), 37)
            self.assertIsNone(latest_runtime(Path(td), 'cts'))


if __name__ == '__main__':
    unittest.main()
