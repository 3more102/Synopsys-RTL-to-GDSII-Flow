#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from rich_qor import (
    metric_value,
    normalize,
    parse_area,
    parse_cts,
    parse_number,
    parse_physical_verification,
    parse_power_detail,
    parse_route,
    parse_timing,
)
from qor_parsers import parse_area_util, parse_congestion, parse_drc, parse_power, parse_qor

FIX = ROOT / "tests" / "fixtures" / "qor"


class RichQorParserTests(unittest.TestCase):
    def fixture(self, name):
        return (FIX / name).read_text(encoding="utf-8")

    def test_clean_setup_timing_with_context_and_units(self):
        result = parse_timing(self.fixture("timing_clean.rpt"), "setup")
        self.assertEqual(result["status"], "PARSED")
        self.assertAlmostEqual(metric_value(result, "setup_wns_ns"), 0.084)
        self.assertAlmostEqual(metric_value(result, "setup_tns_ns"), 0.0)
        self.assertEqual(metric_value(result, "setup_violations"), 0)
        self.assertEqual(result["context"]["scenario"], "FUNC_SS_0P72V_125C")
        self.assertEqual(result["context"]["mode"], "FUNC")
        evidence = result["metrics"]["setup_wns_ns"]["evidence"][0]
        self.assertGreater(evidence["line"], 0)
        self.assertEqual(result["metrics"]["setup_wns_ns"]["unit"], "ns")

    def test_setup_violation(self):
        result = parse_timing(self.fixture("timing_setup_fail.rpt"), "setup")
        self.assertAlmostEqual(metric_value(result, "setup_wns_ns"), -0.042)
        self.assertAlmostEqual(metric_value(result, "setup_tns_ns"), -1.311)
        self.assertEqual(metric_value(result, "setup_violations"), 17)
        self.assertEqual(metric_value(result, "setup_pass"), 0)

    def test_hold_violation_from_detailed_paths(self):
        result = parse_timing(self.fixture("timing_hold_fail.rpt"), "hold")
        self.assertAlmostEqual(metric_value(result, "hold_wns_ns"), -0.013)
        self.assertAlmostEqual(metric_value(result, "hold_tns_ns"), -0.018)
        self.assertEqual(metric_value(result, "hold_violations"), 2)
        self.assertEqual(metric_value(result, "hold_pass"), 0)

    def test_multi_scenario_timing_preserves_sections(self):
        result = parse_timing(self.fixture("timing_multi_scenario.rpt"), "setup")
        self.assertEqual(len(result["scenarios"]), 2)
        by_name = {x["context"]["scenario"]: x for x in result["scenarios"]}
        self.assertAlmostEqual(metric_value(by_name["FUNC_SS"], "setup_wns_ns"), -0.05)
        self.assertAlmostEqual(metric_value(by_name["FUNC_FF"], "setup_wns_ns"), 0.12)

    def test_conflicting_repeated_summary_is_not_silently_selected(self):
        result = parse_timing(self.fixture("timing_conflict.rpt"), "setup")
        self.assertEqual(result["metrics"]["setup_wns_ns"]["status"], "CONFLICT")
        self.assertIsNone(metric_value(result, "setup_wns_ns"))
        self.assertEqual(result["status"], "PARSE_ERROR")

    def test_area_breakdown_counts_macros_commas_and_scientific_notation(self):
        result = parse_area(self.fixture("area_macros.rpt"))
        self.assertEqual(result["status"], "PARSED")
        self.assertAlmostEqual(metric_value(result, "total_cell_area_um2"), 1218000.0)
        self.assertAlmostEqual(metric_value(result, "combinational_area_um2"), 700000.0)
        self.assertAlmostEqual(metric_value(result, "sequential_area_um2"), 318000.0)
        self.assertAlmostEqual(metric_value(result, "macro_area_um2"), 200000.0)
        self.assertEqual(metric_value(result, "cell_count"), 18420)
        self.assertEqual(metric_value(result, "macro_count"), 4)
        self.assertAlmostEqual(metric_value(result, "utilization_ratio"), 0.684)

    def test_power_breakdown_normalizes_units_to_watts(self):
        result = parse_power_detail(self.fixture("power_units.rpt"))
        self.assertAlmostEqual(metric_value(result, "internal_w"), 8.1e-3)
        self.assertAlmostEqual(metric_value(result, "switching_w"), 5700e-6)
        self.assertAlmostEqual(metric_value(result, "leakage_w"), 400000e-9)
        self.assertAlmostEqual(metric_value(result, "total_w"), 14.2e-3)
        self.assertEqual(result["metrics"]["total_w"]["unit"], "W")

    def test_power_table_variant(self):
        result = parse_power_detail(self.fixture("power_table.rpt"))
        self.assertAlmostEqual(metric_value(result, "internal_w"), 0.008)
        self.assertAlmostEqual(metric_value(result, "total_w"), 0.014)

    def test_cts_metrics_and_ps_normalization(self):
        result = parse_cts(self.fixture("cts_normal.rpt"))
        self.assertAlmostEqual(metric_value(result, "clock_skew_ns"), 0.041)
        self.assertAlmostEqual(metric_value(result, "network_latency_ns"), 0.730)
        self.assertAlmostEqual(metric_value(result, "max_transition_ns"), 0.085)
        self.assertEqual(metric_value(result, "sink_count"), 1248)
        self.assertEqual(metric_value(result, "clock_cell_count"), 165)
        self.assertEqual(metric_value(result, "tree_levels"), 9)

    def test_route_metrics(self):
        result = parse_route(self.fixture("route_normal.rpt"))
        self.assertEqual(metric_value(result, "drc_violations"), 0)
        self.assertAlmostEqual(metric_value(result, "wire_length_um"), 1_425_000.0)
        self.assertEqual(metric_value(result, "via_count"), 91234)
        self.assertAlmostEqual(metric_value(result, "horizontal_overflow"), 0.012)
        self.assertAlmostEqual(metric_value(result, "vertical_overflow"), 0.007)
        self.assertAlmostEqual(metric_value(result, "total_overflow"), 0.019)
        self.assertEqual(metric_value(result, "congested_bins"), 18)

    def test_physical_verification_statuses(self):
        drc = parse_physical_verification(self.fixture("drc_violation.rpt"), "drc")
        self.assertEqual(drc["result_status"], "FAIL")
        self.assertEqual(metric_value(drc, "violations"), 3)
        lvs = parse_physical_verification("LVS result: PASS\nLVS mismatch count: 0\n", "lvs")
        self.assertEqual(lvs["result_status"], "PASS")
        self.assertEqual(parse_physical_verification("", "drc")["result_status"], "NOT_RUN")
        self.assertEqual(parse_physical_verification("report generated but no result\n", "lvs")["result_status"], "UNKNOWN")

    def test_empty_unrecognized_and_missing_sections(self):
        self.assertEqual(parse_area("")["status"], "UNRECOGNIZED")
        self.assertEqual(parse_cts("random text\n")["status"], "UNRECOGNIZED")
        partial = parse_area(self.fixture("area_partial.rpt"))
        self.assertEqual(partial["status"], "PARTIAL")
        self.assertIsNone(metric_value(partial, "macro_area_um2"))

    def test_unsupported_unit_is_not_zero(self):
        result = parse_power_detail("Total Power : 9.0 kW\n")
        self.assertIsNone(metric_value(result, "total_w"))
        # Pattern deliberately does not accept kW, avoiding accidental unitless capture.
        self.assertIn(result["status"], {"UNRECOGNIZED", "PARTIAL"})

    def test_numeric_helpers(self):
        self.assertEqual(parse_number("1,234.5e-3"), 1.2345)
        self.assertEqual(normalize(41, "ps", "time"), (0.041, "ns"))
        self.assertEqual(normalize(18.7, "mW", "power"), (0.0187, "W"))
        with self.assertRaises(ValueError):
            normalize(1.0, "kW", "power")

    def test_legacy_facade_remains_compatible(self):
        self.assertEqual(parse_qor("WNS : -0.125\nTNS : -2.75\nNo. of Violating Paths : 14\n"), (-0.125, -2.75, 14))
        self.assertEqual(parse_area_util("Total cell area: 1234.5\nUtilization Ratio: 0.67\nNumber of cells: 842\n"), (1234.5, 0.67, 842))
        self.assertEqual(parse_power("Total Power = 1.25e-03"), 1.25e-3)
        self.assertEqual(parse_congestion("Total Overflow : 3.4"), 3.4)
        self.assertEqual(parse_drc("DRC violations : 7"), 7)


if __name__ == "__main__":
    unittest.main()
