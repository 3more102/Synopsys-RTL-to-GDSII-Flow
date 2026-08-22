import importlib.util
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("plan_rebuild_v2", ROOT / "python" / "plan_rebuild.py")
plan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plan)


class RebuildPlanV2Tests(TestCase):
    def setUp(self):
        self.graph = {
            "schema_version": 2,
            "aliases": {"a-target": "a", "b-target": "b"},
            "stages": {
                "a": {"target": "a-target", "fingerprint": "a", "depends_on": [], "evidence": "checkpoints/a.status"},
                "b": {"target": "b-target", "fingerprint": "b", "depends_on": ["a"], "evidence": "checkpoints/b.status"},
            },
        }
        self.policy = {"schema_version": 1, "stages": {"a": {}, "b": {}}}

    def test_not_run_is_optional_for_advisory_plan(self):
        with tempfile.TemporaryDirectory() as td:
            result = plan.build_plan(Path(td), self.graph, self.policy, None, include_not_run=False)
        self.assertFalse(result["rebuild_required"])
        self.assertEqual(result["execution_targets"], [])

    def test_not_run_becomes_executable_plan_when_requested(self):
        with tempfile.TemporaryDirectory() as td:
            result = plan.build_plan(Path(td), self.graph, self.policy, None, include_not_run=True)
        self.assertTrue(result["rebuild_required"])
        self.assertEqual(result["earliest_rebuild_stage"], "a")
        self.assertEqual(result["execution_targets"], ["a-target", "b-target"])

    def test_stale_upstream_propagates_to_descendants(self):
        states = {"a": ("STALE", "changed"), "b": ("FRESH", "same")}
        with tempfile.TemporaryDirectory() as td, patch.object(plan, "fingerprint_state", side_effect=lambda root, stage, cfg, known: states[stage]):
            result = plan.build_plan(Path(td), self.graph, self.policy, None, include_not_run=False)
        self.assertEqual(result["execution_targets"], ["a-target", "b-target"])

    def test_target_scope_limits_rebuild_cone(self):
        graph = {
            "schema_version": 2,
            "aliases": {},
            "stages": {
                "a": {"target": "a", "fingerprint": "a", "depends_on": [], "evidence": "checkpoints/a"},
                "b": {"target": "b", "fingerprint": "b", "depends_on": ["a"], "evidence": "checkpoints/b"},
                "side": {"target": "side", "fingerprint": "side", "depends_on": ["a"], "evidence": "checkpoints/side"},
            },
        }
        policy = {"schema_version": 1, "stages": {"a": {}, "b": {}, "side": {}}}
        states = {"a": ("FRESH", "same"), "b": ("NOT_RUN", "missing"), "side": ("STALE", "changed")}
        with tempfile.TemporaryDirectory() as td, patch.object(plan, "fingerprint_state", side_effect=lambda root, stage, cfg, known: states[stage]):
            result = plan.build_plan(Path(td), graph, policy, "b", include_not_run=True)
        self.assertEqual(result["execution_targets"], ["b"])
        self.assertNotIn("side", [row["stage"] for row in result["stages"]])


if __name__ == "__main__":
    import unittest
    unittest.main()
