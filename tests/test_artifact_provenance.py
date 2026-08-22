import importlib.util
import json
import os
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("artifact_provenance", ROOT / "python" / "build_artifact_provenance.py")
prov = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prov)


class ArtifactProvenanceTests(unittest.TestCase):
    def graph(self):
        return {
            "schema_version": 2,
            "aliases": {"synth": "synthesis"},
            "stages": {
                "lint": {"target": "lint", "fingerprint": "lint", "depends_on": [], "evidence": "checkpoints/lint/lint.status"},
                "synthesis": {"target": "synth", "fingerprint": "synthesis", "depends_on": ["lint"], "evidence": "checkpoints/synthesis/synthesis.status"},
                "outputs": {"target": "outputs", "fingerprint": "outputs", "depends_on": ["synthesis"], "evidence": "reports/status/final_outputs.status"},
            },
        }

    def contract(self):
        return {
            "schema_version": 1,
            "aliases": {"synth": "synthesis"},
            "stages": {
                "synthesis": {
                    "required": ["results/synthesis/${PROJECT_NAME}_syn.v"],
                    "optional": ["reports/synthesis/*.rpt"],
                },
                "outputs": {"required": ["netlist/${PROJECT_NAME}_postroute.v"]},
            },
        }

    def write_json(self, path: Path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def prepare_synthesis_evidence(self, root: Path):
        out = root / "results" / "synthesis" / "chip_syn.v"
        out.parent.mkdir(parents=True)
        out.write_text("module chip; endmodule\n", encoding="utf-8")
        status = root / "checkpoints" / "synthesis" / "synthesis.status"
        status.parent.mkdir(parents=True)
        status.write_text("status=PASS\ndetail=mapped\n", encoding="utf-8")
        self.write_json(root / "checkpoints" / "fingerprints" / "synthesis.json", {"digest": "synth-digest"})
        self.write_json(root / "checkpoints" / "fingerprints" / "lint.json", {"digest": "lint-digest"})
        self.write_json(
            root / "reports" / "runtime" / "synthesis.latest.json",
            {
                "flow_run_id": "run-001",
                "tool": "dc_shell",
                "tool_path": "/tools/dc_shell",
                "script": "scripts/synthesis/01_synthesis.tcl",
                "start": "2026-08-22T10:00:00Z",
                "end": "2026-08-22T10:01:00Z",
                "duration_seconds": 60,
                "exit_code": 0,
                "git_commit": "abc",
                "git_dirty": False,
                "input_fingerprint": "checkpoints/fingerprints/synthesis.json",
                "input_digest": "synth-digest",
            },
        )
        return out

    def test_manifest_links_artifact_to_runtime_and_fingerprints(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = self.prepare_synthesis_evidence(root)
            manifest = prov.build_manifest(root, self.contract(), self.graph(), "chip", "synth")
            self.assertEqual(len(manifest["artifacts"]), 1)
            item = manifest["artifacts"][0]
            self.assertEqual(item["path"], "results/synthesis/chip_syn.v")
            self.assertEqual(item["stage"], "synthesis")
            self.assertEqual(item["artifact_class"], "required")
            self.assertEqual(item["runtime"]["tool"], "dc_shell")
            self.assertEqual(item["runtime"]["flow_run_id"], "run-001")
            self.assertEqual(item["stage_fingerprint"]["digest"], "synth-digest")
            self.assertEqual(item["upstream_fingerprints"]["lint"]["digest"], "lint-digest")
            self.assertEqual(item["stage_status"], "PASS")
            self.assertEqual(item["sha256"], prov.sha256_file(out))
            self.assertEqual(manifest["stages"]["synthesis"]["missing_required"], [])

    def test_missing_required_is_recorded_without_fabricating_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = prov.build_manifest(root, self.contract(), self.graph(), "chip", "synthesis")
            self.assertEqual(manifest["artifacts"], [])
            self.assertEqual(
                manifest["stages"]["synthesis"]["missing_required"],
                ["results/synthesis/chip_syn.v"],
            )

    def test_stage_refresh_preserves_other_stage_entries(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.prepare_synthesis_evidence(root)
            netlist = root / "netlist" / "chip_postroute.v"
            netlist.parent.mkdir(parents=True)
            netlist.write_text("module chip; endmodule\n", encoding="utf-8")
            first = prov.build_manifest(root, self.contract(), self.graph(), "chip", None)
            self.assertEqual({x["stage"] for x in first["artifacts"]}, {"synthesis", "outputs"})

            netlist.unlink()
            second = prov.build_manifest(root, self.contract(), self.graph(), "chip", "synthesis", existing=first)
            self.assertEqual({x["stage"] for x in second["artifacts"]}, {"synthesis", "outputs"})
            self.assertIn("outputs", second["stages"])

    def test_symlink_outside_root_is_not_manifested(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            root = Path(td)
            ext = Path(outside) / "chip_syn.v"
            ext.write_text("external", encoding="utf-8")
            link = root / "results" / "synthesis" / "chip_syn.v"
            link.parent.mkdir(parents=True)
            try:
                link.symlink_to(ext)
            except OSError:
                self.skipTest("symlink creation unavailable")
            manifest = prov.build_manifest(root, self.contract(), self.graph(), "chip", "synthesis")
            self.assertEqual(manifest["artifacts"], [])
            self.assertEqual(len(manifest["stages"]["synthesis"]["missing_required"]), 1)


if __name__ == "__main__":
    unittest.main()
