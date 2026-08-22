import importlib.util
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("stage_outputs", ROOT / "python" / "validate_stage_outputs.py")
outputs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(outputs)


class StageOutputValidationTests(unittest.TestCase):
    def contract(self, required=None):
        return {
            "schema_version": 1,
            "aliases": {"synth": "synthesis"},
            "stages": {"synthesis": {"required": required or ["results/synthesis/${PROJECT_NAME}_syn.v"]}},
        }

    def graph(self):
        return {"schema_version": 2, "aliases": {"synth": "synthesis"}, "stages": {"synthesis": {}}}

    def test_missing_required_output_fails(self):
        with tempfile.TemporaryDirectory() as td:
            result = outputs.validate_stage(Path(td), "synth", self.contract(), self.graph(), "chip")
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["missing_required"], ["results/synthesis/chip_syn.v"])

    def test_empty_required_output_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "results/synthesis/chip_syn.v"
            path.parent.mkdir(parents=True)
            path.touch()
            result = outputs.validate_stage(root, "synthesis", self.contract(), self.graph(), "chip")
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["invalid_required"][0]["reason"], "file is empty")

    def test_nonempty_required_output_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "results/synthesis/chip_syn.v"
            path.parent.mkdir(parents=True)
            path.write_text("module chip; endmodule\n")
            result = outputs.validate_stage(root, "synthesis", self.contract(), self.graph(), "chip")
            self.assertEqual(result["status"], "PASS")
            self.assertFalse(result["missing_required"])

    def test_symlink_escape_never_satisfies_contract(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as external:
            root = Path(td)
            outside = Path(external) / "chip_syn.v"
            outside.write_text("external netlist")
            link = root / "results/synthesis/chip_syn.v"
            link.parent.mkdir(parents=True)
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("symlinks unavailable")
            result = outputs.validate_stage(root, "synthesis", self.contract(), self.graph(), "chip")
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("escapes project root", result["invalid_required"][0]["reason"])

    def test_glob_requires_at_least_one_valid_match(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            directory = root / "results/synthesis"
            directory.mkdir(parents=True)
            (directory / "empty.v").touch()
            (directory / "good.v").write_text("module good; endmodule\n")
            result = outputs.validate_stage(
                root,
                "synthesis",
                self.contract(["results/synthesis/*.v"]),
                self.graph(),
                "chip",
            )
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["invalid_required"])

    def test_unconfigured_stage_is_skip_not_pass(self):
        with tempfile.TemporaryDirectory() as td:
            result = outputs.validate_stage(Path(td), "route", self.contract(), self.graph(), "chip")
            self.assertEqual(result["status"], "SKIP")
            self.assertFalse(result["configured"])


if __name__ == "__main__":
    unittest.main()
