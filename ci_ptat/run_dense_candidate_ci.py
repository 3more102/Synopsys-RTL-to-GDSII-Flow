#!/usr/bin/env python3
"""Dense SKY130 validation of the selected 1.2 V / 10 nA mirror candidate."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
OUT = RESULTS / "dense_candidate"
REQ = ROOT / "design_requirements.json"
CORNERS = ("tt", "ff", "ss")
VDD = 1.2
IREF = 10e-9
TEMPS = tuple(range(-40, 126, 5))
EXPECTED_REQ_SHA256 = "3ce5222bc2f9fd07dc0ae61727e48c587db58a7b15a6be3df95e1d6ae35bcf7d"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def locate_model() -> Path:
    pdk_root = Path(os.environ.get("PDK_ROOT", "/home/runner/pdk")).expanduser()
    direct = pdk_root / "sky130A" / "libs.tech" / "ngspice" / "sky130.lib.spice"
    if direct.is_file():
        return direct.resolve()
    matches = [p.resolve() for p in pdk_root.glob("**/sky130A/libs.tech/ngspice/sky130.lib.spice") if p.is_file()]
    if not matches:
        raise FileNotFoundError("SKY130 ngspice model not found")
    return sorted(set(matches), key=str)[-1]


def sections(model: Path) -> set[str]:
    pattern = re.compile(r"^\s*\.lib\s+(\S+)", re.I)
    out: set[str] = set()
    for line in model.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = pattern.match(line)
        if m:
            out.add(m.group(1).lower())
    return out


def ngspice_version() -> str:
    p = subprocess.run(["ngspice", "--version"], check=True, text=True, capture_output=True)
    for line in (p.stdout or p.stderr).splitlines():
        clean = line.strip().lstrip("*").strip()
        if clean.lower().startswith("ngspice-"):
            return clean
    raise RuntimeError("ngspice version not found")


def pdk_sources() -> str | None:
    path = Path(os.environ.get("PDK_ROOT", "/home/runner/pdk")) / "sky130A" / "SOURCES"
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.is_file() else None


def deck(model: Path, corner: str, cfg: dict, csv_path: Path) -> str:
    seed = cfg["nominal_characterization_seed"]
    nmos = seed["sensor_nmos"]
    pmos = seed["mirror_pmos"]
    temps = " ".join(str(t) for t in TEMPS)
    return f'''* Dense SKY130 PTAT mirror candidate validation
.lib "{model}" {corner}
.param VDDVAL={VDD:.12g}
.param IREF={IREF:.12g}
.param LNS={nmos["l_um"]:.12g}
.param WNS1={nmos["w_small_um"]:.12g}
.param WNS2={nmos["w_large_um"]:.12g}
.param LPM={pmos["l_um"]:.12g}
.param WPM={pmos["w_um"]:.12g}
.param PTEMP=-40
.temp {{PTEMP}}
VDD vdd 0 DC {{VDDVAL}}
IREFBIAS pref 0 DC {{IREF}}
XMPREF pref pref vdd vdd sky130_fd_pr__pfet_01v8 L={{LPM}} W={{WPM}}
XMP1 p1 pref vdd vdd sky130_fd_pr__pfet_01v8 L={{LPM}} W={{WPM}}
XMP2 p2 pref vdd vdd sky130_fd_pr__pfet_01v8 L={{LPM}} W={{WPM}}
VPROBE1 p1 v1 DC 0
VPROBE2 p2 v2 DC 0
XMN1 v1 v1 0 0 sky130_fd_pr__nfet_01v8 L={{LNS}} W={{WNS1}}
XMN2 v2 v2 0 0 sky130_fd_pr__nfet_01v8 L={{LNS}} W={{WNS2}}
.control
set noaskquit
set numdgt=15
echo "temp_c,vgs_small_v,vgs_large_v,dvgs_v,supply_current_a,power_w,branch_small_a,branch_large_a" > {csv_path}
foreach t {temps}
  alterparam PTEMP = $t
  reset
  op
  let dvgs = v(v1)-v(v2)
  let isupply = -i(VDD)
  let psupply = v(vdd)*isupply
  let i1 = abs(i(VPROBE1))
  let i2 = abs(i(VPROBE2))
  echo $t',' $&v(v1)',' $&v(v2)',' $&dvgs',' $&isupply',' $&psupply',' $&i1',' $&i2 >> {csv_path}
end
quit
.endc
.end
'''


def validate_csv(path: Path) -> dict[str, float]:
    rows: list[dict[str, float]] = []
    with path.open(newline="", encoding="utf-8") as f:
        for raw in csv.DictReader(f, skipinitialspace=True):
            rows.append({k.strip(): float(v.strip()) for k, v in raw.items() if k and v})
    if len(rows) != len(TEMPS):
        raise RuntimeError(f"{path}: expected {len(TEMPS)} rows, got {len(rows)}")
    if [round(r["temp_c"]) for r in rows] != list(TEMPS):
        raise RuntimeError(f"{path}: temperature grid mismatch")
    mismatch = []
    min_headroom = math.inf
    max_power = 0.0
    for row in rows:
        if not all(math.isfinite(x) for x in row.values()):
            raise RuntimeError(f"{path}: non-finite value")
        if abs((row["vgs_small_v"] - row["vgs_large_v"]) - row["dvgs_v"]) > 2e-6:
            raise RuntimeError(f"{path}: dvgs inconsistency")
        if min(row["branch_small_a"], row["branch_large_a"], row["supply_current_a"], row["power_w"]) <= 0:
            raise RuntimeError(f"{path}: non-positive current/power")
        expected_supply = IREF + row["branch_small_a"] + row["branch_large_a"]
        if abs(row["supply_current_a"] - expected_supply) > max(1e-12, 0.02 * expected_supply):
            raise RuntimeError(f"{path}: supply accounting mismatch")
        mean_i = 0.5 * (row["branch_small_a"] + row["branch_large_a"])
        mismatch.append(abs(row["branch_small_a"] - row["branch_large_a"]) / mean_i * 100.0)
        min_headroom = min(min_headroom, VDD - max(row["vgs_small_v"], row["vgs_large_v"]))
        max_power = max(max_power, row["power_w"])
    if min_headroom < 0.1:
        raise RuntimeError(f"{path}: headroom guardband failed")
    if max(mismatch) > 1.0:
        raise RuntimeError(f"{path}: mirror mismatch target failed")
    return {
        "max_abs_branch_mismatch_pct": max(mismatch),
        "min_headroom_v": min_headroom,
        "max_power_w": max_power,
    }


def main() -> int:
    cfg = json.loads(REQ.read_text(encoding="utf-8"))
    req_hash = sha256_file(REQ)
    if req_hash != EXPECTED_REQ_SHA256:
        raise RuntimeError("design requirements hash mismatch")
    model = locate_model()
    model_sections = sections(model)
    if not set(CORNERS).issubset(model_sections):
        raise RuntimeError("PDK missing TT/FF/SS corners")
    OUT.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}
    metrics: dict[str, dict[str, float]] = {}
    for corner in CORNERS:
        csv_path = OUT / f"dense_mirror_{corner}.csv"
        deck_path = ROOT / f"ptat_dense_mirror_{corner}.spice"
        log_path = OUT / f"dense_mirror_{corner}.log"
        deck_path.write_text(deck(model, corner, cfg, csv_path), encoding="utf-8")
        subprocess.run(["ngspice", "-b", "-o", str(log_path), str(deck_path)], cwd=ROOT, check=True)
        log = log_path.read_text(encoding="utf-8", errors="ignore")
        if "ngspice-46 done" not in log or "Simulation interrupted" in log:
            raise RuntimeError(f"{corner}: ngspice completion validation failed")
        metrics[corner] = validate_csv(csv_path)
        for path in (deck_path, log_path, csv_path):
            files[str(path.relative_to(ROOT))] = sha256_file(path)
        print(f"PASS dense {corner}: {metrics[corner]}", flush=True)
    manifest = {
        "status": "PASS",
        "evidence_class": "Dense real SKY130/open_pdks PMOS-mirror PTAT candidate validation",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "candidate": {"vdd_v": VDD, "iref_a": IREF},
        "temperature_grid_c": list(TEMPS),
        "operating_points": len(TEMPS) * len(CORNERS),
        "corners": list(CORNERS),
        "design_requirements_sha256": req_hash,
        "ngspice_version": ngspice_version(),
        "model_path": str(model),
        "model_sha256": sha256_file(model),
        "model_library_sections": sorted(model_sections),
        "pdk_sources": pdk_sources(),
        "corner_metrics": metrics,
        "files_sha256": files,
    }
    out = RESULTS / "sky130_dense_candidate_ci_manifest.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"PASS dense candidate operating_points={manifest['operating_points']}")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
