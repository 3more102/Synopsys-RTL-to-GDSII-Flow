#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DELIVERY = ROOT / "final_delivery"
DEFAULT_PROVENANCE = ROOT / "reports" / "provenance" / "run_provenance.json"
DEFAULT_QOR = ROOT / "reports" / "summary" / "qor_summary.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()


def read_statuses(root: Path) -> dict[str, str]:
    out = {}
    status_dir = root / "reports" / "status"
    if not status_dir.is_dir(): return out
    for p in sorted(status_dir.glob("*.status")):
        status = "UNKNOWN"
        for line in p.read_text(errors="ignore").splitlines():
            if line.startswith("status="): status = line.split("=",1)[1].strip()
        out[p.stem] = status
    return out


def foundry_state(statuses: dict[str,str]) -> str:
    drc = statuses.get("drc", "UNKNOWN"); lvs = statuses.get("lvs", "UNKNOWN")
    if "FAIL" in {drc,lvs}: return "FAIL"
    if drc == "PASS" and lvs == "PASS": return "PASS"
    return "UNKNOWN"


def build(root: Path, delivery: Path, provenance_path: Path, qor_path: Path) -> dict[str, Any]:
    artifacts = []
    if delivery.is_dir():
        for p in sorted(delivery.rglob("*")):
            if not p.is_file() or p.name in {"RELEASE_MANIFEST.json", "checksums.txt"}: continue
            artifacts.append({"path": str(p.relative_to(delivery)), "size": p.stat().st_size, "sha256": sha256_file(p)})
    provenance = json.loads(provenance_path.read_text()) if provenance_path.is_file() else {}
    qor = json.loads(qor_path.read_text()) if qor_path.is_file() else None
    statuses = read_statuses(root)
    return {
        "schema_version": 1,
        "project": os.environ.get("PROJECT_NAME", provenance.get("project", "MIPS_16")),
        "top_module": os.environ.get("TOP_MODULE", provenance.get("top_module", "mips_16")),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provenance_digest": provenance.get("provenance_digest", "UNKNOWN"),
        "git": provenance.get("git", {}),
        "artifacts": artifacts,
        "statuses": statuses,
        "qor": qor,
        "foundry_signoff": foundry_state(statuses),
        "qualification_note": "Foundry signoff is PASS only when both DRC and LVS status evidence are PASS; otherwise it is FAIL or UNKNOWN."
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a machine-readable ASIC final-delivery release manifest.")
    ap.add_argument("--root", default=str(ROOT)); ap.add_argument("--delivery", default=str(DEFAULT_DELIVERY)); ap.add_argument("--provenance", default=str(DEFAULT_PROVENANCE)); ap.add_argument("--qor", default=str(DEFAULT_QOR)); ap.add_argument("--output", default="")
    args = ap.parse_args(); root=Path(args.root).resolve(); delivery=Path(args.delivery).resolve(); output=Path(args.output).resolve() if args.output else delivery/"RELEASE_MANIFEST.json"
    output.parent.mkdir(parents=True, exist_ok=True); result=build(root, delivery, Path(args.provenance), Path(args.qor)); output.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(f"RELEASE_MANIFEST artifacts={len(result['artifacts'])} foundry_signoff={result['foundry_signoff']} output={output}"); return 0

if __name__ == "__main__": raise SystemExit(main())
