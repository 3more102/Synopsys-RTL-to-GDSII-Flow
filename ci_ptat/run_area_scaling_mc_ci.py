#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess

import run_sky130_ci as base
import run_sky130_design_sweeps_ci as sweep

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
RAW = RESULTS / "area_scaling_mc" / "raw"
SUMMARY = RESULTS / "sky130_area_scaling_mc.csv"
MANIFEST = RESULTS / "sky130_area_scaling_mc_manifest.json"
CAL_TEMPS = (-40.0, 25.0, 125.0)
SEEDS = [202700 + 7919 * index for index in range(12)]

# Scale linear W and L together to preserve nominal W/L while increasing area.
VARIANTS = {
    "baseline": {"sensor_linear_scale": 1.0, "mirror_linear_scale": 1.0},
    "mirror_area4x": {"sensor_linear_scale": 1.0, "mirror_linear_scale": 2.0},
    "sensor_area4x": {"sensor_linear_scale": 2.0, "mirror_linear_scale": 1.0},
    "all_area4x": {"sensor_linear_scale": 2.0, "mirror_linear_scale": 2.0},
    "all_area9x": {"sensor_linear_scale": 3.0, "mirror_linear_scale": 3.0},
    "all_area16x": {"sensor_linear_scale": 4.0, "mirror_linear_scale": 4.0},
}


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    pos = q * (len(ordered) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def quadratic_inverse(cal_v: list[float], value: float) -> float:
    out = 0.0
    for i in range(3):
        term = CAL_TEMPS[i]
        for j in range(3):
            if i == j:
                continue
            denom = cal_v[i] - cal_v[j]
            if abs(denom) < 1e-15:
                raise RuntimeError("degenerate three-point calibration voltage")
            term *= (value - cal_v[j]) / denom
        out += term
    return out


def variant_cfg(base_cfg: dict, variant: dict) -> dict:
    cfg = deepcopy(base_cfg)
    seed = cfg["nominal_characterization_seed"]
    seed["vdd_v"] = 1.2
    seed["reference_current_a"] = 1e-8
    sensor_scale = float(variant["sensor_linear_scale"])
    mirror_scale = float(variant["mirror_linear_scale"])
    nmos = seed["sensor_nmos"]
    nmos["l_um"] *= sensor_scale
    nmos["w_small_um"] *= sensor_scale
    nmos["w_large_um"] *= sensor_scale
    pmos = seed["mirror_pmos"]
    pmos["l_um"] *= mirror_scale
    pmos["w_um"] *= mirror_scale
    return cfg


def config_sha256(cfg: dict) -> str:
    data = json.dumps(cfg, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def run_sample(model: Path, cfg: dict, seed_value: int, variant_name: str) -> dict:
    stem = f"{variant_name}_seed_{seed_value}"
    rel_csv = f"area_scaling_mc/raw/{stem}.csv"
    text = base.mirror_deck(model, "tt_mm", cfg, rel_csv)
    needle = f'.lib "{model}" tt_mm\n'
    if needle not in text:
        raise RuntimeError("tt_mm library line missing")
    text = text.replace(needle, f".option seed={seed_value}\n{needle}", 1)
    deck = RAW / f"{stem}.spice"
    log = RAW / f"{stem}.log"
    csv_path = RAW / f"{stem}.csv"
    deck.write_text(text, encoding="utf-8")
    subprocess.run(
        ["ngspice", "-b", "-o", str(log), str(deck)],
        cwd=ROOT,
        check=True,
    )
    rows = base.read_csv(csv_path, mirror=True)
    calibration = sweep.calibration(rows, float(cfg["current_density_ratio"]))
    by_temp = {float(row["temp_c"]): row for row in rows}
    cal_v = [by_temp[temp]["dvgs_v"] for temp in CAL_TEMPS]
    quad_errors = [
        quadratic_inverse(cal_v, row["dvgs_v"]) - row["temp_c"]
        for row in rows
    ]
    mismatches = []
    for row in rows:
        a = row["branch_small_a"]
        b = row["branch_large_a"]
        mismatches.append(100.0 * abs(a - b) / (0.5 * (a + b)))
    vdd = float(cfg["nominal_characterization_seed"]["vdd_v"])
    return {
        "variant": variant_name,
        "seed": seed_value,
        "max_abs_branch_mismatch_pct": max(mismatches),
        "two_point_max_abs_error_c": calibration["two_point_max_abs_error_c"],
        "three_point_max_abs_error_c": max(abs(value) for value in quad_errors),
        "min_headroom_v": min(
            vdd - max(row["vgs_small_v"], row["vgs_large_v"])
            for row in rows
        ),
        "max_power_w": max(row["power_w"] for row in rows),
        "csv_path": str(csv_path.relative_to(ROOT)),
        "csv_sha256": base.sha256_file(csv_path),
        "deck_path": str(deck.relative_to(ROOT)),
        "deck_sha256": base.sha256_file(deck),
        "log_path": str(log.relative_to(ROOT)),
        "log_sha256": base.sha256_file(log),
    }


def main() -> int:
    cfg = base.load_requirements()
    design_hash = base.sha256_file(base.REQ)
    if design_hash != base.EXPECTED_REQ_SHA256:
        raise RuntimeError("base design requirements hash mismatch")
    model = base.locate_model()
    if "tt_mm" not in base.library_sections(model):
        raise RuntimeError("SKY130 model does not expose tt_mm")
    RAW.mkdir(parents=True, exist_ok=True)
    for old in RAW.glob("*"):
        if old.is_file():
            old.unlink()

    samples: list[dict] = []
    variant_configs: dict[str, dict] = {}
    for variant_name, scales in VARIANTS.items():
        vcfg = variant_cfg(cfg, scales)
        variant_configs[variant_name] = {
            "scales": scales,
            "config_sha256": config_sha256(vcfg),
            "sensor_nmos": vcfg["nominal_characterization_seed"]["sensor_nmos"],
            "mirror_pmos": vcfg["nominal_characterization_seed"]["mirror_pmos"],
        }
        for index, seed_value in enumerate(SEEDS, start=1):
            sample = run_sample(model, vcfg, seed_value, variant_name)
            samples.append(sample)
            print(
                f"PASS {variant_name} {index:02d}/{len(SEEDS)} "
                f"seed={seed_value} mismatch="
                f"{sample['max_abs_branch_mismatch_pct']:.3f}%",
                flush=True,
            )

    fields = list(samples[0].keys())
    with SUMMARY.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(samples)

    aggregate: dict[str, dict] = {}
    for name in VARIANTS:
        rows = [row for row in samples if row["variant"] == name]
        mismatch = [float(row["max_abs_branch_mismatch_pct"]) for row in rows]
        two = [float(row["two_point_max_abs_error_c"]) for row in rows]
        three = [float(row["three_point_max_abs_error_c"]) for row in rows]
        aggregate[name] = {
            "sample_count": len(rows),
            "p50_max_abs_branch_mismatch_pct": percentile(mismatch, 0.50),
            "p95_max_abs_branch_mismatch_pct": percentile(mismatch, 0.95),
            "max_abs_branch_mismatch_pct": max(mismatch),
            "p95_two_point_max_abs_error_c": percentile(two, 0.95),
            "p95_three_point_max_abs_error_c": percentile(three, 0.95),
            "three_point_samples_le_0p5c": sum(value <= 0.5 for value in three),
            "min_headroom_v": min(float(row["min_headroom_v"]) for row in rows),
            "max_power_w": max(float(row["max_power_w"]) for row in rows),
        }
    selected = min(
        aggregate,
        key=lambda name: (
            aggregate[name]["p95_three_point_max_abs_error_c"],
            aggregate[name]["p95_max_abs_branch_mismatch_pct"],
        ),
    )

    files_sha256 = {str(SUMMARY.relative_to(ROOT)): base.sha256_file(SUMMARY)}
    for row in samples:
        for kind in ("csv", "deck", "log"):
            files_sha256[row[f"{kind}_path"]] = row[f"{kind}_sha256"]
    manifest = {
        "status": "PASS",
        "evidence_class": (
            "Exploratory SKY130 tt_mm device-area scaling screen; "
            "not foundry statistical signoff or a yield claim"
        ),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "base_design_requirements_sha256": design_hash,
        "ngspice_version": base.ngspice_version(),
        "model_sha256": base.sha256_file(model),
        "pdk_sources": base.pdk_sources(model),
        "candidate_vdd_v": 1.2,
        "candidate_iref_a": 1e-8,
        "seed_list": SEEDS,
        "calibration_temperatures_c": list(CAL_TEMPS),
        "variant_configs": variant_configs,
        "aggregate": aggregate,
        "screen_selected_variant": selected,
        "summary": {
            "path": str(SUMMARY.relative_to(ROOT)),
            "sha256": base.sha256_file(SUMMARY),
            "rows": len(samples),
        },
        "files_sha256": files_sha256,
        "scope_note": (
            "This screen changes device dimensions experimentally without "
            "changing the released design_requirements.json. A winning sizing "
            "must be promoted into a new physical-design hash and rerun before "
            "it can replace baseline signoff evidence."
        ),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"selected": selected, "aggregate": aggregate}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
