import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_flow_model", ROOT / "python" / "validate_flow_model.py")
mod = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(mod)


class FlowModelConsistencyTests(unittest.TestCase):
    def make_repo(self, td: str, make_target: str = "build") -> Path:
        root = Path(td); (root / "config").mkdir(); (root / "Makefile").write_text(f"{make_target}:\n\t@true\n", encoding="utf-8")
        (root / "config" / "stage_graph.json").write_text(json.dumps({"schema_version": 2, "aliases": {make_target: "stage"}, "stages": {"stage": {"target": make_target, "fingerprint": "stage", "depends_on": [], "evidence": "checkpoints/stage/status"}}}), encoding="utf-8")
        (root / "config" / "fingerprint_policy.json").write_text(json.dumps({"schema_version": 1, "aliases": {make_target: "stage"}, "stages": {"stage": {}}}), encoding="utf-8")
        (root / "config" / "artifact_provenance.json").write_text(json.dumps({"schema_version": 1, "aliases": {make_target: "stage"}, "stages": {"stage": {"required": ["out/${PROJECT_NAME}.v"], "optional": ["reports/stage/*.rpt"]}}}), encoding="utf-8")
        (root / "config" / "stage_contracts.json").write_text(json.dumps({"schema_version": 1, "required_artifacts": [{"path": "out/${PROJECT_NAME}.v", "min_bytes": 1}], "optional_artifacts": [{"path": "reports/stage/qor.rpt", "min_bytes": 1}], "required_status": {}, "advisory_status": {}, "strict_signoff_status": {}}), encoding="utf-8")
        return root

    def test_consistent_model_passes(self):
        with tempfile.TemporaryDirectory() as td:
            errors, warnings = mod.validate(self.make_repo(td))
        self.assertEqual(errors, []); self.assertTrue(any("common core stages" in w for w in warnings))

    def test_missing_make_target_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_repo(td); graph_path = root / "config/stage_graph.json"; graph = json.loads(graph_path.read_text()); graph["stages"]["stage"]["target"] = "missing"; graph_path.write_text(json.dumps(graph))
            errors, _ = mod.validate(root)
        self.assertTrue(any("missing Make target" in e for e in errors))

    def test_fingerprint_target_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_repo(td); fp_path = root / "config/fingerprint_policy.json"; fp = json.loads(fp_path.read_text()); fp["aliases"]["build"] = "other"; fp["stages"]["other"] = {}; fp_path.write_text(json.dumps(fp))
            errors, _ = mod.validate(root)
        self.assertTrue(any("expects 'stage'" in e for e in errors))

    def test_cycle_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_repo(td); graph_path = root / "config/stage_graph.json"; graph = json.loads(graph_path.read_text())
            graph["stages"]["other"] = {"target": "other", "fingerprint": "other", "depends_on": ["stage"], "evidence": "checkpoints/other/status"}; graph["stages"]["stage"]["depends_on"] = ["other"]; graph["aliases"]["other"] = "other"; graph_path.write_text(json.dumps(graph))
            with (root / "Makefile").open("a") as f: f.write("other:\n\t@true\n")
            fp_path = root / "config/fingerprint_policy.json"; fp = json.loads(fp_path.read_text()); fp["aliases"]["other"] = "other"; fp["stages"]["other"] = {}; fp_path.write_text(json.dumps(fp))
            errors, _ = mod.validate(root)
        self.assertTrue(any("cycle detected" in e for e in errors))

    def test_artifact_contract_stage_must_exist_in_dag(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_repo(td); path = root / "config/artifact_provenance.json"; cfg = json.loads(path.read_text()); cfg["stages"]["ghost"] = {"required": ["ghost/out.v"]}; path.write_text(json.dumps(cfg))
            errors, _ = mod.validate(root)
        self.assertTrue(any("ghost" in e and "absent" in e for e in errors))

    def test_required_output_cannot_have_two_stage_owners(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_repo(td); graph_path = root / "config/stage_graph.json"; graph = json.loads(graph_path.read_text()); graph["stages"]["other"] = {"target": "other", "fingerprint": "other", "depends_on": ["stage"], "evidence": "checkpoints/other/status"}; graph["aliases"]["other"] = "other"; graph_path.write_text(json.dumps(graph))
            with (root / "Makefile").open("a") as f: f.write("other:\n\t@true\n")
            fp_path = root / "config/fingerprint_policy.json"; fp = json.loads(fp_path.read_text()); fp["aliases"]["other"] = "other"; fp["stages"]["other"] = {}; fp_path.write_text(json.dumps(fp))
            art_path = root / "config/artifact_provenance.json"; art = json.loads(art_path.read_text()); art["stages"]["other"] = {"required": ["out/${PROJECT_NAME}.v"]}; art_path.write_text(json.dumps(art))
            errors, _ = mod.validate(root)
        self.assertTrue(any("multiple owners" in e for e in errors))

    def test_release_required_artifact_must_be_required_in_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_repo(td); art_path = root / "config/artifact_provenance.json"; art = json.loads(art_path.read_text()); art["stages"]["stage"] = {"optional": ["out/${PROJECT_NAME}.v", "reports/stage/*.rpt"]}; art_path.write_text(json.dumps(art))
            errors, _ = mod.validate(root)
        self.assertTrue(any("only optional" in e for e in errors))

    def test_release_artifact_without_provenance_owner_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_repo(td); rel_path = root / "config/stage_contracts.json"; rel = json.loads(rel_path.read_text()); rel["optional_artifacts"].append({"path": "unowned/evidence.txt"}); rel_path.write_text(json.dumps(rel))
            errors, _ = mod.validate(root)
        self.assertTrue(any("no artifact provenance policy owner" in e for e in errors))

    def test_unsafe_artifact_pattern_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_repo(td); art_path = root / "config/artifact_provenance.json"; art = json.loads(art_path.read_text()); art["stages"]["stage"]["optional"].append("../escape.rpt"); art_path.write_text(json.dumps(art))
            errors, _ = mod.validate(root)
        self.assertTrue(any("unsafe" in e for e in errors))


if __name__ == "__main__": unittest.main()
