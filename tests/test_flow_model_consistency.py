import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_flow_model", ROOT / "python" / "validate_flow_model.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class FlowModelConsistencyTests(unittest.TestCase):
    def make_repo(self, td: str, make_target: str = "build") -> Path:
        root = Path(td)
        (root / "config").mkdir()
        (root / "Makefile").write_text(f"{make_target}:\n\t@true\n", encoding="utf-8")
        (root / "config" / "stage_graph.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "aliases": {make_target: "stage"},
                    "stages": {
                        "stage": {
                            "target": make_target,
                            "fingerprint": "stage",
                            "depends_on": [],
                            "evidence": "checkpoints/stage/status",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        (root / "config" / "fingerprint_policy.json").write_text(
            json.dumps({"schema_version": 1, "aliases": {make_target: "stage"}, "stages": {"stage": {}}}),
            encoding="utf-8",
        )
        return root

    def test_consistent_model_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_repo(td)
            errors, warnings = mod.validate(root)
        self.assertEqual(errors, [])
        self.assertTrue(any("common core stages" in w for w in warnings))

    def test_missing_make_target_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_repo(td, make_target="build")
            graph_path = root / "config" / "stage_graph.json"
            graph = json.loads(graph_path.read_text())
            graph["stages"]["stage"]["target"] = "missing"
            graph_path.write_text(json.dumps(graph), encoding="utf-8")
            errors, _ = mod.validate(root)
        self.assertTrue(any("missing Make target" in e for e in errors))

    def test_fingerprint_target_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_repo(td)
            fp_path = root / "config" / "fingerprint_policy.json"
            fp = json.loads(fp_path.read_text())
            fp["aliases"]["build"] = "other"
            fp["stages"]["other"] = {}
            fp_path.write_text(json.dumps(fp), encoding="utf-8")
            errors, _ = mod.validate(root)
        self.assertTrue(any("expects 'stage'" in e for e in errors))

    def test_cycle_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_repo(td)
            graph_path = root / "config" / "stage_graph.json"
            graph = json.loads(graph_path.read_text())
            graph["stages"]["other"] = {
                "target": "other",
                "fingerprint": "other",
                "depends_on": ["stage"],
                "evidence": "checkpoints/other/status",
            }
            graph["stages"]["stage"]["depends_on"] = ["other"]
            graph["aliases"]["other"] = "other"
            graph_path.write_text(json.dumps(graph), encoding="utf-8")
            with (root / "Makefile").open("a", encoding="utf-8") as f:
                f.write("other:\n\t@true\n")
            fp_path = root / "config" / "fingerprint_policy.json"
            fp = json.loads(fp_path.read_text())
            fp["aliases"]["other"] = "other"
            fp["stages"]["other"] = {}
            fp_path.write_text(json.dumps(fp), encoding="utf-8")
            errors, _ = mod.validate(root)
        self.assertTrue(any("cycle detected" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
