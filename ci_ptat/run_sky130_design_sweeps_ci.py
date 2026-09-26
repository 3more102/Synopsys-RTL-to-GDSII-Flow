#!/usr/bin/env python3
from __future__ import annotations

import csv
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess

import run_sky130_ci as base

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
IDEAL_RAW = RESULTS / "design_sweep" / "raw"
MIRROR_RAW = RESULTS / "mirror_design_sweep" / "raw"
IDEAL_SUMMARY = RESULTS / "sky130_design_sweep.csv"
MIRROR_SUMMARY = RESULTS / "sky130_mirror_design_sweep.csv"
MANIFEST = RESULTS / "sky130_design_sweeps_ci_manifest.json"

CORNERS = ("tt", "ff", "ss")
VDDS = (1.2, 1.5, 1.8)
CURRENTS = (10e-9, 30e-9, 100e-9, 300e-9, 1e-6)
TEMPS = base.TEMPS
K_OVER_Q = base.K_B_OVER_Q
N_ANALYTICAL = 1.4


def slug(value: float) -> str:
    return f"{value:.3e}".replace("+", "").replace("-", "m").replace(".", "p")


def run_point(deck_text: str, raw_dir: Path, stem: str) -> tuple[Path, Path, Path]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    deck = raw_dir / f"{stem}.spice"
    log = raw_dir / f"{stem}.log"
    csv_path = raw_dir / f"{stem}.csv"
    deck.write_text(deck_text, encoding="utf-8")
    subprocess.run(["ngspice", "-b", "-o", str(log), str(deck)], cwd=ROOT, check=True)
    if not csv_path.is_file():
        raise RuntimeError(f"missing output CSV: {csv_path}")
    return deck, log, csv_path


def fit_line(xs: list[float], ys: list[float]) -> tuple[float, float]:
    xb = sum(xs) / len(xs)
    yb = sum(ys) / len(ys)
    denom = sum((x - xb) ** 2 for x in xs)
    slope = sum((x - xb) * (y - yb) for x, y in zip(xs, ys)) / denom
    return slope, yb - slope * xb


def rms(values: list[float]) -> float:
    return math.sqrt(sum(v * v for v in values) / len(values))


def percentile95_abs(values: list[float]) -> float:
    vals = sorted(abs(v) for v in values)
    pos = 0.95 * (len(vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    frac = pos - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def calibration(rows: list[dict[str, float]], ratio: float) -> dict[str, float]:
    slope_nom = N_ANALYTICAL * K_OVER_Q * math.log(ratio)
    by_t = {round(r["temp_c"]): r["dvgs_v"] for r in rows}
    vcal = by_t[25]
    v1 = by_t[-20]
    v2 = by_t[100]
    gain2 = 120.0 / (v2 - v1)
    uncal_err: list[float] = []
    one_err: list[float] = []
    two_err: list[float] = []
    for r in rows:
        t = r["temp_c"]
        v = r["dvgs_v"]
        uncal_err.append(v / slope_nom - 273.15 - t)
        one_err.append(25.0 + (v - vcal) / slope_nom - t)
        two_err.append(-20.0 + (v - v1) * gain2 - t)
    out: dict[str, float] = {}
    for name, values in (("uncalibrated", uncal_err), ("one_point", one_err), ("two_point", two_err)):
        out[f"{name}_max_abs_error_c"] = max(abs(v) for v in values)
        out[f"{name}_rms_error_c"] = rms(values)
        out[f"{name}_mean_error_c"] = sum(values) / len(values)
        out[f"{name}_p95_abs_error_c"] = percentile95_abs(values)
    return out


def common_metrics(rows: list[dict[str, float]], vdd: float, ratio: float) -> dict[str, float | bool]:
    xs = [r["temp_c"] for r in rows]
    ys = [r["dvgs_v"] for r in rows]
    slope, intercept = fit_line(xs, ys)
    if slope <= 0:
        raise RuntimeError(f"non-PTAT slope: {slope}")
    residuals = [y - (slope * x + intercept) for x, y in zip(xs, ys)]
    nominal = N_ANALYTICAL * K_OVER_Q * math.log(ratio)
    min_headroom = min(vdd - max(r["vgs_small_v"], r["vgs_large_v"]) for r in rows)
    currents = [r["supply_current_a"] for r in rows]
    powers = [r["power_w"] for r in rows]
    for r in rows:
        if r["vgs_small_v"] > vdd + 5e-3 or r["vgs_large_v"] > vdd + 5e-3:
            raise RuntimeError("sensor node exceeds VDD")
        if abs(r["power_w"] - vdd * r["supply_current_a"]) > max(1e-12, abs(r["power_w"]) * 1e-5):
            raise RuntimeError("power is inconsistent with VDD * IDD")
    return {
        "slope_uv_per_c": slope * 1e6,
        "dvgs_25c_v": next(r["dvgs_v"] for r in rows if round(r["temp_c"]) == 25),
        "max_nonlinearity_uv": max(abs(x) for x in residuals) * 1e6,
        "effective_n_from_slope": slope / (K_OVER_Q * math.log(ratio)),
        "slope_error_vs_analytical_pct": 100.0 * (slope - nominal) / nominal,
        "min_ideal_current_source_headroom_v": min_headroom,
        "headroom_guardband_v": 0.1,
        "headroom_guardband_ok": min_headroom >= 0.1,
        "mean_supply_current_a": sum(currents) / len(currents),
        "mean_power_w": sum(powers) / len(powers),
        "max_power_w": max(powers),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise RuntimeError(f"no rows for {path}")
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def artifact_hashes(paths: list[Path]) -> dict[str, str]:
    return {str(p.relative_to(ROOT)): base.sha256_file(p) for p in paths}


def main() -> int:
    cfg = base.load_requirements()
    design_hash = base.sha256_file(base.REQ)
    if design_hash != base.EXPECTED_REQ_SHA256:
        raise RuntimeError("design requirements hash mismatch")
    model = base.locate_model()
    sections = base.library_sections(model)
    missing = [c for c in CORNERS if c not in sections]
    if missing:
        raise RuntimeError(f"PDK missing corners: {missing}")
    for directory in (IDEAL_RAW, MIRROR_RAW):
        directory.mkdir(parents=True, exist_ok=True)
        for old in directory.glob("*"):
            if old.is_file():
                old.unlink()
    ratio = float(cfg["current_density_ratio"])
    ideal_summary: list[dict] = []
    mirror_summary: list[dict] = []
    evidence_files: list[Path] = []
    for corner in CORNERS:
        for vdd in VDDS:
            for ibias in CURRENTS:
                point_cfg = deepcopy(cfg)
                seed = point_cfg["nominal_characterization_seed"]
                seed["vdd_v"] = vdd
                seed["branch_current_a"] = ibias
                stem = f"sky130_{corner}_vdd_{slug(vdd)}_ibias_{slug(ibias)}"
                rel_csv = f"design_sweep/raw/{stem}.csv"
                deck, log, csv_path = run_point(base.ideal_deck(model, corner, point_cfg, rel_csv), IDEAL_RAW, stem)
                rows = base.read_csv(csv_path, mirror=False)
                metrics = common_metrics(rows, vdd, ratio)
                expected_supply = 2.0 * ibias
                current_error = 100.0 * (metrics["mean_supply_current_a"] - expected_supply) / expected_supply
                if abs(current_error) > 1.0:
                    raise RuntimeError(f"ideal current accounting error {current_error}%")
                cal = calibration(rows, ratio)
                ideal_summary.append({"corner":corner,"vdd_v":vdd,"ibias_a":ibias,"slope_uv_per_c":metrics["slope_uv_per_c"],"dvgs_25c_v":metrics["dvgs_25c_v"],"max_nonlinearity_uv":metrics["max_nonlinearity_uv"],"effective_n_from_slope":metrics["effective_n_from_slope"],"slope_error_vs_analytical_pct":metrics["slope_error_vs_analytical_pct"],"min_ideal_current_source_headroom_v":metrics["min_ideal_current_source_headroom_v"],"headroom_guardband_v":metrics["headroom_guardband_v"],"headroom_guardband_ok":metrics["headroom_guardband_ok"],"mean_supply_current_a":metrics["mean_supply_current_a"],"mean_ideal_bias_power_w":metrics["mean_power_w"],"max_ideal_bias_power_w":metrics["max_power_w"],"supply_current_error_pct":current_error,"uncalibrated_max_abs_error_c":cal["uncalibrated_max_abs_error_c"],"one_point_max_abs_error_c":cal["one_point_max_abs_error_c"],"two_point_max_abs_error_c":cal["two_point_max_abs_error_c"],"two_point_rms_error_c":cal["two_point_rms_error_c"],"raw_csv":str(csv_path.relative_to(ROOT)),"raw_sha256":base.sha256_file(csv_path)})
                evidence_files += [deck, log, csv_path]
                print(f"PASS ideal {corner} VDD={vdd:g} IBIAS={ibias:.3g}", flush=True)
    for corner in CORNERS:
        for vdd in VDDS:
            for iref in CURRENTS:
                point_cfg = deepcopy(cfg)
                seed = point_cfg["nominal_characterization_seed"]
                seed["vdd_v"] = vdd
                seed["reference_current_a"] = iref
                stem = f"sky130_mirror_{corner}_vdd_{slug(vdd)}_iref_{slug(iref)}"
                rel_csv = f"mirror_design_sweep/raw/{stem}.csv"
                deck, log, csv_path = run_point(base.mirror_deck(model, corner, point_cfg, rel_csv), MIRROR_RAW, stem)
                rows = base.read_csv(csv_path, mirror=True)
                metrics = common_metrics(rows, vdd, ratio)
                i1 = [r["branch_small_a"] for r in rows]
                i2 = [r["branch_large_a"] for r in rows]
                mismatches = [100.0 * (a - b) / (0.5 * (a + b)) for a, b in zip(i1, i2)]
                tracking1 = [100.0 * (a - iref) / iref for a in i1]
                tracking2 = [100.0 * (b - iref) / iref for b in i2]
                expected_supply = [iref + a + b for a, b in zip(i1, i2)]
                supply = [r["supply_current_a"] for r in rows]
                accounting = [100.0 * (m - e) / e for m, e in zip(supply, expected_supply)]
                if max(abs(x) for x in accounting) > 2.0:
                    raise RuntimeError("mirror supply-current accounting exceeds 2%")
                cal = calibration(rows, ratio)
                mirror_summary.append({"corner":corner,"vdd_v":vdd,"iref_a":iref,"slope_uv_per_c":metrics["slope_uv_per_c"],"effective_n_from_slope":metrics["effective_n_from_slope"],"slope_error_vs_analytical_pct":metrics["slope_error_vs_analytical_pct"],"dvgs_25c_v":metrics["dvgs_25c_v"],"max_nonlinearity_uv":metrics["max_nonlinearity_uv"],"min_mirror_headroom_v":metrics["min_ideal_current_source_headroom_v"],"headroom_guardband_ok":metrics["headroom_guardband_ok"],"max_abs_branch_mismatch_pct":max(abs(x) for x in mismatches),"rms_branch_mismatch_pct":rms(mismatches),"max_abs_small_tracking_error_pct":max(abs(x) for x in tracking1),"max_abs_large_tracking_error_pct":max(abs(x) for x in tracking2),"mean_supply_current_a":sum(supply)/len(supply),"mean_core_plus_mirror_power_w":metrics["mean_power_w"],"max_core_plus_mirror_power_w":metrics["max_power_w"],"one_point_max_abs_error_c":cal["one_point_max_abs_error_c"],"two_point_max_abs_error_c":cal["two_point_max_abs_error_c"],"two_point_rms_error_c":cal["two_point_rms_error_c"],"raw_csv":str(csv_path.relative_to(ROOT)),"raw_sha256":base.sha256_file(csv_path)})
                evidence_files += [deck, log, csv_path]
                print(f"PASS mirror {corner} VDD={vdd:g} IREF={iref:.3g}", flush=True)
    ideal_summary.sort(key=lambda r:(r["corner"],r["vdd_v"],r["ibias_a"]))
    mirror_summary.sort(key=lambda r:(r["corner"],r["vdd_v"],r["iref_a"]))
    write_csv(IDEAL_SUMMARY, ideal_summary)
    write_csv(MIRROR_SUMMARY, mirror_summary)
    evidence_files += [IDEAL_SUMMARY, MIRROR_SUMMARY]
    qualified=[r for r in mirror_summary if r["headroom_guardband_ok"] and r["max_abs_branch_mismatch_pct"]<=float(cfg["mirror_branch_mismatch_percent_max"]) and r["one_point_max_abs_error_c"]<=float(cfg["total_one_point_max_abs_error_c_target"]) and r["two_point_max_abs_error_c"]<=float(cfg["total_two_point_max_abs_error_c_target"])]
    manifest={"status":"PASS","evidence_class":"real SKY130/open_pdks ngspice CI design-space characterization","generated_utc":datetime.now(timezone.utc).isoformat(),"design_requirements_sha256":design_hash,"ngspice_version":base.ngspice_version(),"model_path":str(model),"model_sha256":base.sha256_file(model),"model_library_sections":sorted(sections),"pdk_sources":base.pdk_sources(model),"sweep":{"corners":list(CORNERS),"vdd_v":list(VDDS),"currents_a":list(CURRENTS),"temperature_c":list(TEMPS)},"ideal_summary":{"path":str(IDEAL_SUMMARY.relative_to(ROOT)),"sha256":base.sha256_file(IDEAL_SUMMARY),"rows":len(ideal_summary)},"mirror_summary":{"path":str(MIRROR_SUMMARY.relative_to(ROOT)),"sha256":base.sha256_file(MIRROR_SUMMARY),"rows":len(mirror_summary)},"qualifying_mirror_configurations":len(qualified),"qualifying_mirror_rows":qualified,"files_sha256":artifact_hashes(evidence_files)}
    MANIFEST.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"PASS","ideal_configurations":len(ideal_summary),"mirror_configurations":len(mirror_summary),"qualifying_mirror_configurations":len(qualified),"manifest":str(MANIFEST)},indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
