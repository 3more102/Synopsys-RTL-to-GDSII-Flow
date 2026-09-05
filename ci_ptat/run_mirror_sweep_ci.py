#!/usr/bin/env python3
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
SWEEP_DIR = RESULTS / "mirror_design_sweep"
RAW_DIR = SWEEP_DIR / "raw"
SUMMARY = RESULTS / "sky130_mirror_design_sweep.csv"
MANIFEST = RESULTS / "sky130_mirror_design_sweep_manifest.json"
REQ = ROOT / "design_requirements.json"
CORNERS = ("tt", "ff", "ss")
VDDS = (1.2, 1.5, 1.8)
IREFS = (10e-9, 30e-9, 100e-9, 300e-9, 1e-6)
TEMPS = (-40, -20, 0, 25, 50, 75, 100, 125)
K_B_OVER_Q = 8.617333262145e-5
NOMINAL_N = 1.4
DENSITY_RATIO = 8.0
EXPECTED_REQ_SHA256 = "3ce5222bc2f9fd07dc0ae61727e48c587db58a7b15a6be3df95e1d6ae35bcf7d"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_requirements() -> dict:
    return json.loads(REQ.read_text(encoding="utf-8"))


def locate_model() -> Path:
    pdk_root = Path(os.environ.get("PDK_ROOT", "/home/runner/pdk")).expanduser()
    direct = pdk_root / "sky130A" / "libs.tech" / "ngspice" / "sky130.lib.spice"
    if direct.is_file():
        return direct.resolve()
    candidates = list(pdk_root.glob("**/sky130A/libs.tech/ngspice/sky130.lib.spice"))
    files = [p.resolve() for p in candidates if p.is_file()]
    if not files:
        raise FileNotFoundError(f"SKY130 ngspice model not found below {pdk_root}")
    return sorted(set(files), key=str)[-1]


def library_sections(model: Path) -> set[str]:
    sections: set[str] = set()
    pattern = re.compile(r"^\s*\.lib\s+(\S+)", re.IGNORECASE)
    for line in model.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = pattern.match(line)
        if match:
            sections.add(match.group(1).lower())
    return sections


def ngspice_version() -> str:
    proc = subprocess.run(
        ["ngspice", "--version"],
        check=True,
        text=True,
        capture_output=True,
    )
    lines = (proc.stdout or proc.stderr).splitlines()
    for line in lines:
        line = line.strip().lstrip("*").strip()
        if line.lower().startswith("ngspice-"):
            return line
    raise RuntimeError("Could not parse ngspice version")


def pdk_sources(model: Path) -> str | None:
    pdk_root = Path(os.environ.get("PDK_ROOT", "/home/runner/pdk")).expanduser()
    direct = pdk_root / "sky130A" / "SOURCES"
    if direct.is_file():
        return direct.read_text(encoding="utf-8", errors="ignore").strip()
    for parent in model.parents:
        source = parent / "SOURCES"
        if source.is_file():
            return source.read_text(encoding="utf-8", errors="ignore").strip()
    return None


def deck_text(model: Path, corner: str, cfg: dict, aggregate_csv: Path) -> str:
    seed = cfg["nominal_characterization_seed"]
    nmos = seed["sensor_nmos"]
    pmos = seed["mirror_pmos"]
    vdds = " ".join(f"{v:.12g}" for v in VDDS)
    irefs = " ".join(f"{i:.12g}" for i in IREFS)
    temps = " ".join(str(t) for t in TEMPS)
    return f'''* SKY130 PTAT PMOS-mirror design sweep, CI evidence
.lib "{model}" {corner}
.param VDDVAL=1.8
.param IREF=1e-7
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
echo "vdd_v,iref_a,temp_c,vgs_small_v,vgs_large_v,dvgs_v,supply_current_a,power_w,branch_small_a,branch_large_a" > {aggregate_csv}
foreach vv {vdds}
  alterparam VDDVAL = $vv
  foreach ii {irefs}
    alterparam IREF = $ii
    foreach tt {temps}
      alterparam PTEMP = $tt
      reset
      op
      let dvgs = v(v1)-v(v2)
      let isupply = -i(VDD)
      let psupply = v(vdd)*isupply
      let ibranch1 = abs(i(VPROBE1))
      let ibranch2 = abs(i(VPROBE2))
      echo $vv',' $ii',' $tt',' $&v(v1)',' $&v(v2)',' $&dvgs',' $&isupply',' $&psupply',' $&ibranch1',' $&ibranch2 >> {aggregate_csv}
    end
  end
end
quit
.endc
.end
'''


def run_deck(text: str, corner: str) -> tuple[Path, Path, Path]:
    deck = ROOT / f"ptat_mirror_sweep_{corner}.spice"
    log = SWEEP_DIR / f"ptat_mirror_sweep_{corner}.log"
    aggregate = SWEEP_DIR / f"ptat_mirror_sweep_{corner}_aggregate.csv"
    deck.write_text(text, encoding="utf-8")
    subprocess.run(["ngspice", "-b", "-o", str(log), str(deck)], cwd=ROOT, check=True)
    log_text = log.read_text(encoding="utf-8", errors="ignore")
    if "ngspice-46 done" not in log_text:
        raise RuntimeError(f"ngspice completion marker missing for {corner}")
    if "Simulation interrupted" in log_text:
        raise RuntimeError(f"simulation interrupted for {corner}")
    if not aggregate.is_file():
        raise RuntimeError(f"aggregate CSV missing for {corner}")
    return deck, log, aggregate


def load_aggregate(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, skipinitialspace=True)
        for raw in reader:
            row = {
                k.strip(): float(v.strip())
                for k, v in raw.items()
                if k is not None and v is not None
            }
            rows.append(row)
    expected = len(VDDS) * len(IREFS) * len(TEMPS)
    if len(rows) != expected:
        raise RuntimeError(f"{path}: expected {expected} rows, got {len(rows)}")
    return rows


def calibration_metrics(group: list[dict[str, float]]) -> tuple[float, float, float]:
    by_t = {round(row["temp_c"]): row for row in group}
    if set(by_t) != set(TEMPS):
        raise RuntimeError("temperature grid mismatch")
    nominal_slope = NOMINAL_N * K_B_OVER_Q * math.log(DENSITY_RATIO)
    v25 = by_t[25]["dvgs_v"]
    one_errors = [
        (25.0 + (row["dvgs_v"] - v25) / nominal_slope) - row["temp_c"]
        for row in group
    ]
    va = by_t[-20]["dvgs_v"]
    vb = by_t[100]["dvgs_v"]
    two_slope = (vb - va) / 120.0
    if two_slope <= 0:
        raise RuntimeError("non-positive two-point calibration slope")
    two_errors = [
        (-20.0 + (row["dvgs_v"] - va) / two_slope) - row["temp_c"]
        for row in group
    ]
    one_max = max(abs(e) for e in one_errors)
    two_max = max(abs(e) for e in two_errors)
    two_rms = math.sqrt(sum(e * e for e in two_errors) / len(two_errors))
    return one_max, two_max, two_rms


def summarize(group: list[dict[str, float]], corner: str, vdd: float, iref: float) -> dict:
    group = sorted(group, key=lambda row: row["temp_c"])
    if [round(row["temp_c"]) for row in group] != list(TEMPS):
        raise RuntimeError("temperature ordering mismatch")
    for row in group:
        if not all(math.isfinite(v) for v in row.values()):
            raise RuntimeError("non-finite sweep value")
        if abs((row["vgs_small_v"] - row["vgs_large_v"]) - row["dvgs_v"]) > 2e-6:
            raise RuntimeError("inconsistent dvgs")
        if row["branch_small_a"] <= 0 or row["branch_large_a"] <= 0:
            raise RuntimeError("non-positive branch current")
        expected_supply = iref + row["branch_small_a"] + row["branch_large_a"]
        if abs(row["supply_current_a"] - expected_supply) > max(1e-12, 0.02 * expected_supply):
            raise RuntimeError("supply current accounting mismatch")

    xs = [row["temp_c"] for row in group]
    ys = [row["dvgs_v"] for row in group]
    xbar = sum(xs) / len(xs)
    ybar = sum(ys) / len(ys)
    denom = sum((x - xbar) ** 2 for x in xs)
    slope = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys)) / denom
    intercept = ybar - slope * xbar
    residuals = [y - (slope * x + intercept) for x, y in zip(xs, ys)]
    if slope <= 0:
        raise RuntimeError("non-PTAT slope")
    n_eff = slope / (K_B_OVER_Q * math.log(DENSITY_RATIO))
    mismatch = []
    for row in group:
        mean_i = 0.5 * (row["branch_small_a"] + row["branch_large_a"])
        mismatch.append(abs(row["branch_small_a"] - row["branch_large_a"]) / mean_i * 100.0)
    min_headroom = min(vdd - max(row["vgs_small_v"], row["vgs_large_v"]) for row in group)
    one_max, two_max, two_rms = calibration_metrics(group)
    return {
        "corner": corner,
        "vdd_v": vdd,
        "iref_a": iref,
        "slope_uv_per_c": slope * 1e6,
        "effective_n_from_slope": n_eff,
        "dvgs_25c_v": next(row["dvgs_v"] for row in group if round(row["temp_c"]) == 25),
        "max_nonlinearity_uv": max(abs(v) for v in residuals) * 1e6,
        "min_mirror_headroom_v": min_headroom,
        "headroom_guardband_ok": min_headroom >= 0.1,
        "max_abs_branch_mismatch_pct": max(mismatch),
        "mean_supply_current_a": sum(row["supply_current_a"] for row in group) / len(group),
        "max_core_plus_mirror_power_w": max(row["power_w"] for row in group),
        "one_point_max_abs_error_c": one_max,
        "two_point_max_abs_error_c": two_max,
        "two_point_rms_error_c": two_rms,
    }


def slug(value: float) -> str:
    return f"{value:.3e}".replace("+", "").replace("-", "m").replace(".", "p")


def write_point_csv(path: Path, group: list[dict[str, float]]) -> None:
    fields = [
        "temp_c", "vgs_small_v", "vgs_large_v", "dvgs_v",
        "supply_current_a", "power_w", "branch_small_a", "branch_large_a",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in sorted(group, key=lambda item: item["temp_c"]):
            writer.writerow({field: f"{row[field]:.15g}" for field in fields})


def main() -> int:
    cfg = load_requirements()
    design_hash = sha256_file(REQ)
    if design_hash != EXPECTED_REQ_SHA256:
        raise RuntimeError("design_requirements.json hash does not match v12 release")
    model = locate_model()
    sections = library_sections(model)
    if not set(CORNERS).issubset(sections):
        raise RuntimeError("SKY130 model missing TT/FF/SS sections")

    SWEEP_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for path in list(RAW_DIR.glob("*")) + list(SWEEP_DIR.glob("*_aggregate.csv")):
        if path.is_file():
            path.unlink()

    all_rows: list[dict] = []
    files_sha: dict[str, str] = {}
    raw_outputs: list[dict] = []
    for corner in CORNERS:
        aggregate = SWEEP_DIR / f"ptat_mirror_sweep_{corner}_aggregate.csv"
        text = deck_text(model, corner, cfg, aggregate)
        deck, log, aggregate = run_deck(text, corner)
        rows = load_aggregate(aggregate)
        for vdd in VDDS:
            for iref in IREFS:
                group = [
                    row for row in rows
                    if abs(row["vdd_v"] - vdd) < 1e-9
                    and abs(row["iref_a"] - iref) < max(1e-15, iref * 1e-9)
                ]
                if len(group) != len(TEMPS):
                    raise RuntimeError(f"missing point rows for {corner} VDD={vdd} IREF={iref}")
                point = summarize(group, corner, vdd, iref)
                name = f"sky130_mirror_{corner}_vdd_{slug(vdd)}_iref_{slug(iref)}.csv"
                path = RAW_DIR / name
                write_point_csv(path, group)
                point["raw_csv"] = str(path.relative_to(ROOT))
                point["raw_sha256"] = sha256_file(path)
                all_rows.append(point)
                raw_outputs.append({
                    "path": point["raw_csv"],
                    "sha256": point["raw_sha256"],
                    "corner": corner,
                    "vdd_v": vdd,
                    "iref_a": iref,
                })
        for path in (deck, log, aggregate):
            files_sha[str(path.relative_to(ROOT))] = sha256_file(path)

    fields = [
        "corner", "vdd_v", "iref_a", "slope_uv_per_c",
        "effective_n_from_slope", "dvgs_25c_v", "max_nonlinearity_uv",
        "min_mirror_headroom_v", "headroom_guardband_ok",
        "max_abs_branch_mismatch_pct", "mean_supply_current_a",
        "max_core_plus_mirror_power_w", "one_point_max_abs_error_c",
        "two_point_max_abs_error_c", "two_point_rms_error_c",
        "raw_csv", "raw_sha256",
    ]
    with SUMMARY.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in sorted(all_rows, key=lambda x: (x["corner"], x["vdd_v"], x["iref_a"])):
            writer.writerow(row)

    for entry in raw_outputs:
        files_sha[entry["path"]] = entry["sha256"]
    files_sha[str(SUMMARY.relative_to(ROOT))] = sha256_file(SUMMARY)

    manifest = {
        "status": "PASS",
        "evidence_class": "SKY130/ngspice PMOS-mirror PTAT design sweep",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "design_requirements_sha256": design_hash,
        "ngspice_version": ngspice_version(),
        "model_path": str(model),
        "model_sha256": sha256_file(model),
        "model_library_sections": sorted(sections),
        "pdk_sources": pdk_sources(model),
        "sweep": {
            "corners": list(CORNERS),
            "vdd_v": list(VDDS),
            "iref_a": list(IREFS),
            "temperature_c": list(TEMPS),
            "configurations": len(all_rows),
            "operating_points": len(all_rows) * len(TEMPS),
        },
        "summary": {
            "path": str(SUMMARY.relative_to(ROOT)),
            "sha256": sha256_file(SUMMARY),
            "rows": len(all_rows),
        },
        "raw_outputs": raw_outputs,
        "files_sha256": files_sha,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"PASS mirror design sweep configurations={len(all_rows)} operating_points={len(all_rows)*len(TEMPS)}")
    print(f"PASS summary={SUMMARY}")
    print(f"PASS manifest={MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
