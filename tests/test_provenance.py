import json
import os
import tempfile
import unittest
from pathlib import Path

from build_provenance import build
from compare_provenance import compare


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "rtl").mkdir(); (self.root / "constraints").mkdir(); (self.root / "scripts").mkdir(); (self.root / "config").mkdir(); (self.root / "reports" / "capabilities").mkdir(parents=True)
        (self.root / "rtl" / "top.v").write_text("module top; endmodule\n")
        (self.root / "constraints" / "top.sdc").write_text("create_clock -period 10 [get_ports clk]\n")
        (self.root / "scripts" / "flow.tcl").write_text("puts flow\n")
        (self.root / "config" / "technology.tcl").write_text("set TECH TEST\n")
        self.policy = {
            "schema_version": 1,
            "external_path_mode": "stat",
            "groups": {
                "design": {"files": ["rtl/*.v", "constraints/*.sdc"], "env": ["CLOCK_PERIOD"]},
                "methodology": {"files": ["scripts/*.tcl"], "env": []},
                "technology": {"files": ["config/technology.tcl"], "env": [], "external_env_paths": ["TARGET_LIBRARY"]},
                "execution": {"files": [], "env": ["DC_SHELL"]}
            },
            "comparison_severity": {"design":"FAIL", "methodology":"FAIL", "technology":"FAIL", "execution":"WARNING"}
        }
        self.old = dict(os.environ)
        os.environ["CLOCK_PERIOD"] = "10"
        os.environ["DC_SHELL"] = "missing-dc"
        os.environ["TARGET_LIBRARY"] = ""

    def tearDown(self):
        os.environ.clear(); os.environ.update(self.old); self.tmp.cleanup()

    def test_stable_inputs_stable_group_digests(self):
        a = build(self.root, self.policy); b = build(self.root, self.policy)
        self.assertEqual(a["group_digests"], b["group_digests"])
        self.assertEqual(a["provenance_digest"], b["provenance_digest"])

    def test_rtl_change_only_changes_design_identity(self):
        a = build(self.root, self.policy)
        (self.root / "rtl" / "top.v").write_text("module top; wire x; endmodule\n")
        b = build(self.root, self.policy)
        self.assertNotEqual(a["group_digests"]["design"], b["group_digests"]["design"])
        self.assertEqual(a["group_digests"]["methodology"], b["group_digests"]["methodology"])

    def test_script_change_changes_methodology_identity(self):
        a = build(self.root, self.policy)
        (self.root / "scripts" / "flow.tcl").write_text("puts changed\n")
        b = build(self.root, self.policy)
        self.assertNotEqual(a["group_digests"]["methodology"], b["group_digests"]["methodology"])

    def test_design_difference_blocks_comparison(self):
        a = build(self.root, self.policy)
        (self.root / "rtl" / "top.v").write_text("module top; logic x; endmodule\n")
        b = build(self.root, self.policy)
        r = compare(a, b, self.policy)
        self.assertEqual(r["status"], "FAIL")
        self.assertEqual(r["groups"]["design"]["state"], "DIFF")

    def test_execution_difference_is_warning_by_default(self):
        a = build(self.root, self.policy)
        os.environ["DC_SHELL"] = "other-missing-dc"
        b = build(self.root, self.policy)
        r = compare(a, b, self.policy)
        self.assertEqual(r["status"], "WARNING")
        self.assertEqual(r["groups"]["execution"]["state"], "DIFF")

    def test_strict_execution_blocks_tool_difference(self):
        a = build(self.root, self.policy)
        os.environ["DC_SHELL"] = "other-missing-dc"
        b = build(self.root, self.policy)
        self.assertEqual(compare(a, b, self.policy, strict_execution=True)["status"], "FAIL")


if __name__ == "__main__": unittest.main()
