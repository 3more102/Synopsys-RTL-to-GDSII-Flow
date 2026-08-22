import unittest
from probe_capabilities import summarize


class CapabilitySummaryTests(unittest.TestCase):
    def test_unavailable_is_unknown(self):
        status, failures, unknowns = summarize({"dc": {"status": "UNAVAILABLE", "commands": {}}})
        self.assertEqual(status, "UNKNOWN")
        self.assertFalse(failures)
        self.assertTrue(unknowns)

    def test_missing_required_command_is_fail(self):
        status, failures, unknowns = summarize({"dc": {"status": "AVAILABLE", "commands": {"compile_ultra": {"required": True, "supported": False}}}})
        self.assertEqual(status, "FAIL")
        self.assertTrue(failures)
        self.assertFalse(unknowns)

    def test_all_required_commands_present_is_pass(self):
        status, failures, unknowns = summarize({"pt": {"status": "AVAILABLE", "commands": {"report_timing": {"required": True, "supported": True}}}})
        self.assertEqual(status, "PASS")
        self.assertFalse(failures)
        self.assertFalse(unknowns)


if __name__ == "__main__":
    unittest.main()
