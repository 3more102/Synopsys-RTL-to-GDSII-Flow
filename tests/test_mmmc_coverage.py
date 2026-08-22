import tempfile
import unittest
from pathlib import Path

from validate_mmmc_coverage import audit


POLICY = {
    "schema_version": 1,
    "required_purposes_per_enabled_mode": ["setup", "hold"],
    "require_corner_library_for_enabled_scenario": True,
    "require_mode_sdc_for_enabled_mode": True,
    "require_enabled_mode_for_enabled_scenario": True,
    "expected_rc_by_purpose": {"setup":"max", "hold":"min"},
    "scenario_report_templates": {"setup":"reports/signoff/scenarios/{scenario}/setup.rpt", "hold":"reports/signoff/scenarios/{scenario}/hold.rpt"}
}


class MMMCCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        (self.root/"constraints").mkdir(); (self.root/"lib").mkdir(); (self.root/"constraints"/"top.sdc").write_text("create_clock -period 10 [get_ports clk]\n")
        (self.root/"lib"/"ss.db").write_text("x"); (self.root/"lib"/"ff.db").write_text("x")
    def tearDown(self): self.tmp.cleanup()
    def base(self, enabled=True):
        return {"corners":{"SS":{"purpose":"setup","rc":"max","lib":"lib/ss.db"},"FF":{"purpose":"hold","rc":"min","lib":"lib/ff.db"}},"modes":{"functional":{"enabled":True,"sdc":"constraints/top.sdc"}},"scenarios":{"func_setup":{"enabled":enabled,"mode":"functional","corner":"SS"},"func_hold":{"enabled":enabled,"mode":"functional","corner":"FF"}}}
    def test_disabled_conceptual_scenarios_are_unknown_not_fail(self):
        r=audit(self.root,self.base(False),POLICY); self.assertEqual(r["status"],"UNKNOWN")
    def test_complete_setup_hold_coverage_passes(self):
        r=audit(self.root,self.base(True),POLICY); self.assertEqual(r["status"],"PASS")
    def test_missing_hold_coverage_fails(self):
        d=self.base(True); d["scenarios"]["func_hold"]["enabled"]=False
        r=audit(self.root,d,POLICY); self.assertEqual(r["status"],"FAIL"); self.assertIn("MODE_COVERAGE_INCOMPLETE",[f["code"] for f in r["findings"]])
    def test_missing_corner_library_fails(self):
        d=self.base(True); d["corners"]["SS"]["lib"]=""
        r=audit(self.root,d,POLICY); self.assertIn("ENABLED_SCENARIO_NO_LIBRARY",[f["code"] for f in r["findings"]])
    def test_rc_role_mismatch_fails(self):
        d=self.base(True); d["corners"]["SS"]["rc"]="min"
        r=audit(self.root,d,POLICY); self.assertIn("RC_ROLE_MISMATCH",[f["code"] for f in r["findings"]])
    def test_required_evidence_detects_missing_report(self):
        r=audit(self.root,self.base(True),POLICY,require_evidence=True); self.assertEqual(r["status"],"FAIL"); self.assertIn("SCENARIO_EVIDENCE_MISSING",[f["code"] for f in r["findings"]])
    def test_required_evidence_passes_when_reports_exist(self):
        for s,p in (("func_setup","setup"),("func_hold","hold")):
            q=self.root/"reports"/"signoff"/"scenarios"/s/f"{p}.rpt"; q.parent.mkdir(parents=True,exist_ok=True); q.write_text("report\n")
        r=audit(self.root,self.base(True),POLICY,require_evidence=True); self.assertEqual(r["status"],"PASS")
    def test_require_enabled_fails_when_none_enabled(self):
        r=audit(self.root,self.base(False),POLICY,require_enabled=True); self.assertEqual(r["status"],"FAIL"); self.assertIn("NO_ENABLED_SCENARIOS",[f["code"] for f in r["findings"]])

if __name__ == "__main__": unittest.main()
