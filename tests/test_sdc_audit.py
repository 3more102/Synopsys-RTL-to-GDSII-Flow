import tempfile
import unittest
from pathlib import Path

from sdc_audit import audit


POLICY = {
    "schema_version": 1,
    "fail_severities": ["ERROR"],
    "require_primary_clock": True,
    "broad_collection_commands": ["get_ports", "get_pins", "get_cells", "get_nets", "get_clocks"],
    "risky_commands": ["set_false_path", "set_multicycle_path", "set_disable_timing", "set_clock_groups", "set_max_delay", "set_min_delay"],
    "ignore_codes": []
}


class SDCAuditTests(unittest.TestCase):
    def write(self, text):
        td = tempfile.TemporaryDirectory()
        p = Path(td.name)
        (p / "top.sdc").write_text(text)
        return td, p

    def test_clean_clock_passes(self):
        td, p = self.write("create_clock -period 10 [get_ports clk]\n")
        try:
            r = audit(p, POLICY)
            self.assertEqual(r["status"], "PASS")
            self.assertEqual(r["counts"]["ERROR"], 0)
        finally:
            td.cleanup()

    def test_global_false_path_fails(self):
        td, p = self.write("create_clock -period 10 [get_ports clk]\nset_false_path\n")
        try:
            r = audit(p, POLICY)
            self.assertEqual(r["status"], "FAIL")
            self.assertIn("GLOBAL_FALSE_PATH", [f["code"] for f in r["findings"]])
        finally:
            td.cleanup()

    def test_broad_wildcard_exception_fails(self):
        td, p = self.write("create_clock -period 10 [get_ports clk]\nset_false_path -from [get_pins *] -to [get_ports out]\n")
        try:
            r = audit(p, POLICY)
            self.assertEqual(r["status"], "FAIL")
            self.assertIn("BROAD_WILDCARD_EXCEPTION", [f["code"] for f in r["findings"]])
        finally:
            td.cleanup()

    def test_missing_clock_fails(self):
        td, p = self.write("set_input_delay 1.0 -clock clk [all_inputs]\n")
        try:
            r = audit(p, POLICY)
            self.assertEqual(r["status"], "FAIL")
            self.assertIn("NO_CREATE_CLOCK", [f["code"] for f in r["findings"]])
        finally:
            td.cleanup()

    def test_multicycle_missing_hold_warns(self):
        td, p = self.write("create_clock -period 10 [get_ports clk]\nset_multicycle_path 2 -setup -from [get_cells A] -to [get_cells B]\n")
        try:
            r = audit(p, POLICY)
            self.assertEqual(r["status"], "PASS")
            self.assertIn("MULTICYCLE_HOLD_PAIR_MISSING", [f["code"] for f in r["findings"]])
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
