import json
import os
import tempfile
import unittest
from pathlib import Path

from stage_fingerprint import collect, load_policy, resolve_stage


class StageFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "rtl").mkdir()
        (self.root / "scripts").mkdir()
        (self.root / "rtl" / "top.v").write_text("module top; endmodule\n")
        (self.root / "scripts" / "synth.tcl").write_text("puts synth\n")
        self.policy_path = self.root / "policy.json"
        self.policy_path.write_text(json.dumps({
            "schema_version": 1,
            "external_path_mode": "stat",
            "common_env": ["PROJECT_NAME"],
            "common_external_env_paths": [],
            "aliases": {"synth": "synthesis"},
            "stages": {"synthesis": {"files": ["rtl/*.v", "scripts/*.tcl"], "env": ["CLOCK_PERIOD"], "tool_env": "DC_SHELL"}}
        }))
        self.old = dict(os.environ)
        os.environ["PROJECT_NAME"] = "T"
        os.environ["CLOCK_PERIOD"] = "10"
        os.environ["DC_SHELL"] = "definitely-not-installed"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old)
        self.tmp.cleanup()

    def test_alias_resolution(self):
        p = load_policy(self.policy_path)
        self.assertEqual(resolve_stage(p, "synth"), "synthesis")

    def test_same_inputs_same_digest(self):
        p = load_policy(self.policy_path)
        a = collect(self.root, p, "synth")
        b = collect(self.root, p, "synthesis")
        self.assertEqual(a["digest"], b["digest"])

    def test_source_change_changes_digest(self):
        p = load_policy(self.policy_path)
        a = collect(self.root, p, "synthesis")
        (self.root / "rtl" / "top.v").write_text("module top; wire x; endmodule\n")
        b = collect(self.root, p, "synthesis")
        self.assertNotEqual(a["digest"], b["digest"])

    def test_env_change_changes_digest(self):
        p = load_policy(self.policy_path)
        a = collect(self.root, p, "synthesis")
        os.environ["CLOCK_PERIOD"] = "8"
        b = collect(self.root, p, "synthesis")
        self.assertNotEqual(a["digest"], b["digest"])


if __name__ == "__main__":
    unittest.main()
