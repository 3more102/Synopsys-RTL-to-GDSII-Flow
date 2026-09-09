#!/usr/bin/env python3
from __future__ import annotations

import copy
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import shutil

import run_sky130_ci as base

ROOT = Path(__file__).resolve().parent
NATIVE = ROOT / "native_sweep"
RESULTS = NATIVE / "results"
RAW = RESULTS / "mirror_design_sweep" / "raw"
SOURCE = NATIVE / "source"
SUMMARY = RESULTS / "sky130_mirror_design_sweep.csv"
MANIFEST = RESULTS / "sky130_mirror_design_sweep_manifest.json"
CORNERS = ("tt", "ff", "ss")
VDDS = (1.2, 1.5, 1.8)
IREFS = (10e-9, 30e-9, 100e-9, 300e-9, 1e-6)


def slug(value: float) -> str:
    return f"{value:.3e}".replace("+", "").replace("-", "m").replace(".", "p")


def calibration(rows: list[dict[str, float]], ratio: float) -> dict[str, float]:
    temps = [r["temp_c"] for r in rows]
    volts = [r["dvgs_v"] for r in rows]
    nominal_slope = 1.4 * base.K_B_OVER_Q * math.log(ratio)
    i25 = temps.index(25.0)
    im20 = temps.index(-20.0)
    i100 = temps.index(100.0)
    one = [25.0 + (v - volts[i25]) / nominal_slope for v in volts]
    two_gain = 120.0 / (volts[i100] - volts[im20])
    two = [-20.0 + (v - volts[im20]) * two_gain for v in volts]
    one_err = [e - t for e, t in zip(one, temps)]
    two_err = [e - t for e, t in zip(two, temps)]
    return {
        "one_point_max_abs_error_c": max(abs(x) for x in one_err),
        "two_point_max_abs_error_c": max(abs(x) for x in two_err),
        "two_point_rms_error_c": math.sqrt(sum(x*x for x in two_err) / len(two_err)),
    }


def summarize(rows: list[dict[str, float]], cfg: dict) -> dict:
    base_metrics = base.fit_metrics(rows, cfg, mirror=True)
    ratio = float(cfg["current_density_ratio"])
    seed = cfg["nominal_characterization_seed"]
    i1 = [r["branch_small_a"] for r in rows]
    i2 = [r["branch_large_a"] for r in rows]
    mismatch = []
    for a, b in zip(i1, i2):
        mean = 0.5 * (a + b)
        mismatch.append(abs(a - b) / mean * 100.0)
    return {
        "slope_uv_per_c": base_metrics["ptat_slope_uv_per_k"],
        "effective_n_from_slope": base_metrics["effective_n"],
        "dvgs_25c_v": base_metrics["dvgs_25c_mv"] / 1000.0,
        "max_nonlinearity_c": base_metrics["max_abs_nonlinearity_c"],
        "min_mirror_headroom_v": base_metrics["min_sensor_headroom_v"],
        "headroom_guardband_ok": bool(base_metrics["headroom_pass"]),
        "max_abs_branch_mismatch_pct": max(mismatch),
        "mean_supply_current_a": sum(r["supply_current_a"] for r in rows) / len(rows),
        "mean_core_plus_mirror_power_w": sum(r["power_w"] for r in rows) / len(rows),
        "max_core_plus_mirror_power_w": max(r["power_w"] for r in rows),
        **calibration(rows, ratio),
        "configured_iref_a": float(seed["reference_current_a"]),
        "configured_vdd_v": float(seed["vdd_v"]),
    }


def main() -> int:
    shutil.rmtree(NATIVE, ignore_errors=True)
    RAW.mkdir(parents=True, exist_ok=True)
    SOURCE.mkdir(parents=True, exist_ok=True)
    base.RESULTS = RESULTS

    cfg0 = base.load_requirements()
    design_hash = base.sha256_file(base.REQ)
    if design_hash != base.EXPECTED_REQ_SHA256:
        raise RuntimeError("design_requirements hash mismatch")
    model = base.locate_model()
    sections = base.library_sections(model)
    missing = [c for c in CORNERS if c not in sections]
    if missing:
        raise RuntimeError(f"model missing corners: {missing}")

    summary_rows: list[dict] = []
    raw_outputs: list[dict] = []
    failures: list[dict] = []
    for corner in CORNERS:
        for vdd in VDDS:
            for iref in IREFS:
                cfg = copy.deepcopy(cfg0)
                seed = cfg["nominal_characterization_seed"]
                seed["vdd_v"] = vdd
                seed["reference_current_a"] = iref
                stem = f"mirror_{corner}_vdd_{slug(vdd)}_iref_{slug(iref)}"
                rel_csv = f"mirror_design_sweep/raw/{stem}.csv"
                try:
                    text = base.mirror_deck(model, corner, cfg, rel_csv)
                    deck, log = base.run_deck(text, stem)
                    csv_path = RESULTS / rel_csv
                    rows = base.read_csv(csv_path, mirror=True)
                    metrics = summarize(rows, cfg)
                    dst_deck = SOURCE / f"{stem}.spice"
                    shutil.copy2(deck, dst_deck)
                    dst_log = RAW / f"{stem}.log"
                    shutil.move(log, dst_log)
                    row = {
                        "corner": corner,
                        "vdd_v": vdd,
                        "iref_a": iref,
                        **metrics,
                        "raw_csv": f"results/{rel_csv}",
                        "raw_sha256": base.sha256_file(csv_path),
                    }
                    summary_rows.append(row)
                    raw_outputs.append({
                        "path": row["raw_csv"],
                        "sha256": row["raw_sha256"],
                        "corner": corner,
                        "vdd_v": vdd,
                        "iref_a": iref,
                        "log_path": f"results/mirror_design_sweep/raw/{stem}.log",
                        "log_sha256": base.sha256_file(dst_log),
                        "deck_path": f"source/{stem}.spice",
                        "deck_sha256": base.sha256_file(dst_deck),
                    })
                    print(f"PASS {corner} VDD={vdd} IREF={iref}")
                except Exception as exc:
                    failures.append({
                        "corner": corner,
                        "vdd_v": vdd,
                        "iref_a": iref,
                        "error": str(exc),
                    })
                    print(f"FAIL {corner} VDD={vdd} IREF={iref}: {exc}")

    if not summary_rows:
        raise RuntimeError("no sweep point produced valid evidence")
    fields = list(summary_rows[0].keys())
    with SUMMARY.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    manifest = {
        "status": "PASS" if not failures else "PARTIAL",
        "evidence_class": "real SKY130/open_pdks PMOS-mirror PTAT design sweep",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "design_requirements_sha256": design_hash,
        "ngspice_version": base.ngspice_version(),
        "model_path": str(model),
        "model_sha256": base.sha256_file(model),
        "pdk_sources": base.pdk_sources(model),
        "sweep": {
            "corners": list(CORNERS),
            "vdd_v": list(VDDS),
            "iref_a": list(IREFS),
            "temperature_c": base.TEMPS,
            "attempted_points": len(CORNERS) * len(VDDS) * len(IREFS),
            "successful_points": len(summary_rows),
            "failed_points": len(failures),
        },
        "summary": {
            "path": "results/sky130_mirror_design_sweep.csv",
            "sha256": base.sha256_file(SUMMARY),
            "rows": len(summary_rows),
        },
        "raw_outputs": raw_outputs,
        "failures": failures,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["sweep"], indent=2))
    return 0 if not failures else 3


if __name__ == "__main__":
    raise SystemExit(main())
