import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("triage_failure", ROOT / "python" / "triage_failure.py")
triage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(triage)


class FailureTriageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.signatures = triage.load_signatures(ROOT / "config" / "failure_signatures.json")

    def test_license_failure_has_high_priority(self):
        text = "ERROR: license checkout failed for feature XYZ\nERROR: file not found later.rpt\n"
        findings = triage.classify(text, self.signatures)
        self.assertGreaterEqual(len(findings), 2)
        self.assertEqual(findings[0]["id"], "license_unavailable")

    def test_output_contract_failure_has_dedicated_category(self):
        text = (
            "MISSING_REQUIRED_OUTPUT=results/synthesis/chip_syn.v\n"
            "ERROR: required stage output contract failed for synthesis; tool exit code was 0\n"
        )
        findings = triage.classify(text, self.signatures)
        self.assertTrue(findings)
        self.assertEqual(findings[0]["id"], "required_output_missing_or_invalid")
        self.assertEqual(findings[0]["category"], "artifact_output")

    def test_missing_input_classifies(self):
        findings = triage.classify("ERROR: required SPEF file not found: /tmp/a.spef\n", self.signatures)
        ids = {item["id"] for item in findings}
        self.assertIn("required_input_missing", ids)

    def test_unknown_failure_remains_unclassified(self):
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "stage.log"
            log.write_text("A completely novel failure token 918273\n", encoding="utf-8")
            result = triage.build_result(log, "route", "icc2_shell", 1, self.signatures)
        self.assertEqual(result["classification_status"], "UNCLASSIFIED")
        self.assertFalse(result["root_cause_proven"])
        self.assertEqual(result["findings"], [])

    def test_evidence_is_bounded(self):
        text = "\n".join(["ERROR: file not found: a" for _ in range(20)])
        findings = triage.classify(text, self.signatures, max_evidence=3)
        missing = next(item for item in findings if item["id"] == "required_input_missing")
        self.assertEqual(missing["hit_count"], 20)
        self.assertEqual(len(missing["evidence"]), 3)

    def test_result_never_claims_root_cause(self):
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "formality.log"
            log.write_text("Verification failed: non-equivalent\n", encoding="utf-8")
            result = triage.build_result(log, "formality", "fm_shell", 1, self.signatures)
        self.assertFalse(result["root_cause_proven"])
        self.assertEqual(result["confidence"], "heuristic")
        self.assertEqual(result["primary_category"], "formal_equivalence")


if __name__ == "__main__":
    unittest.main()
