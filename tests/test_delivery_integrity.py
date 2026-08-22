import importlib.util
import hashlib
import json
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_delivery_integrity", ROOT / "python" / "verify_delivery_integrity.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class DeliveryIntegrityTests(unittest.TestCase):
    def make_package(self, root: Path) -> Path:
        delivery = root / "final_delivery"
        delivery.mkdir()
        artifact = delivery / "chip.gds"
        artifact.write_bytes(b"gds-data")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        manifest = {
            "schema_version": 1,
            "project": "TEST",
            "top_module": "top",
            "provenance_digest": "abc",
            "foundry_signoff": "UNKNOWN",
            "artifacts": [{"path": "chip.gds", "size": artifact.stat().st_size, "sha256": digest}],
        }
        manifest_path = delivery / "RELEASE_MANIFEST.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        (delivery / "checksums.txt").write_text(f"{digest}  ./chip.gds\n{manifest_hash}  ./RELEASE_MANIFEST.json\n", encoding="utf-8")
        return delivery

    def test_valid_package_passes(self):
        with tempfile.TemporaryDirectory() as td:
            delivery = self.make_package(Path(td))
            result = mod.verify(delivery, strict_extra=True)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["checked_manifest_artifacts"], 1)

    def test_modified_artifact_fails(self):
        with tempfile.TemporaryDirectory() as td:
            delivery = self.make_package(Path(td))
            (delivery / "chip.gds").write_bytes(b"modified")
            result = mod.verify(delivery, strict_extra=True)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("mismatch" in e for e in result["errors"]))

    def test_missing_artifact_fails(self):
        with tempfile.TemporaryDirectory() as td:
            delivery = self.make_package(Path(td))
            (delivery / "chip.gds").unlink()
            result = mod.verify(delivery, strict_extra=True)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("missing" in e for e in result["errors"]))

    def test_unexpected_file_warns_or_fails_by_policy(self):
        with tempfile.TemporaryDirectory() as td:
            delivery = self.make_package(Path(td))
            (delivery / "extra.txt").write_text("x", encoding="utf-8")
            relaxed = mod.verify(delivery, strict_extra=False)
            strict = mod.verify(delivery, strict_extra=True)
        self.assertEqual(relaxed["status"], "WARNING")
        self.assertEqual(strict["status"], "FAIL")

    def test_qualified_mode_requires_foundry_pass(self):
        with tempfile.TemporaryDirectory() as td:
            delivery = self.make_package(Path(td))
            result = mod.verify(delivery, strict_extra=True, require_qualified=True)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("foundry_signoff" in e for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
