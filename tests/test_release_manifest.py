import json
import tempfile
import unittest
from pathlib import Path

from build_release_manifest import build, foundry_state


class ReleaseManifestTests(unittest.TestCase):
    def test_foundry_state(self):
        self.assertEqual(foundry_state({"drc":"PASS", "lvs":"PASS"}), "PASS")
        self.assertEqual(foundry_state({"drc":"FAIL", "lvs":"PASS"}), "FAIL")
        self.assertEqual(foundry_state({"drc":"PASS", "lvs":"UNKNOWN"}), "UNKNOWN")

    def test_artifact_inventory_hashes_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); delivery = root / "final_delivery"; delivery.mkdir()
            (delivery / "chip.gds").write_bytes(b"gds")
            (root / "reports" / "status").mkdir(parents=True)
            (root / "reports" / "status" / "drc.status").write_text("status=PASS\n")
            (root / "reports" / "status" / "lvs.status").write_text("status=PASS\n")
            prov = root / "prov.json"; prov.write_text(json.dumps({"project":"P", "top_module":"top", "provenance_digest":"abc", "git":{}}))
            result = build(root, delivery, prov, root / "missing_qor.json")
            self.assertEqual(result["foundry_signoff"], "PASS")
            self.assertEqual(result["provenance_digest"], "abc")
            self.assertEqual(result["artifacts"][0]["path"], "chip.gds")
            self.assertEqual(len(result["artifacts"][0]["sha256"]), 64)


if __name__ == "__main__": unittest.main()
