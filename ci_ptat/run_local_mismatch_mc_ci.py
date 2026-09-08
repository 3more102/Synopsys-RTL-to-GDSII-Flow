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
import run_sky130_design_sweeps_ci as sweep

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
RAW = RESULTS / "local_mismatch_mc" / "raw"
SUMMARY = RESULTS / "sky130_local_mismatch_mc.csv"
MANIFEST = RESULTS / "sky130_local_mismatch_mc_manifest.json"

# Fixed deterministic seed list for reproducibility.  This is an exploratory
# local-mismatch study, not foundry statistical signoff or a yield claim.
SEEDS = [202700 + 7919 * index for index in range(40)]
REPEAT_SEED = SEEDS[0]
CAL_TEMPS = (-40.0, 25.0, 125.0)


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
    # Lagrange interpolation of temperature as a quadratic function of dVGS.
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


def run_seed(model: Path, cfg: dict, seed: int, tag: str) -> dict:
    raw_dir = RAW
    raw_dir.mkdir(parents=True, exist_ok=True)
    stem = f"tt_mm_seed_{seed}_{tag}"
    rel_csv = f"local_mismatch_mc/raw/{stem}.csv"
    text = base.mirror_deck(model, "tt_mm", cfg, rel_csv)
    needle = f'.lib "{model}" tt_mm\n'
    if needle not in text:
        raise RuntimeError("tt_mm library line missing from generated deck")
    text = text.replace(
        needle,
        f".option seed={seed}\n{needle}",
        1,
    )
    deck = raw_dir / f"{stem}.spice"
    log = raw_dir / f"{stem}.log"
    csv_path = raw_dir / f"{stem}.csv"
    deck.write_text(text, encoding="utf-8")
    subprocess.run(
        ["ngspice", "-b", "-o", str(log), str(deck)],
        cwd=ROOT,
        check=True,
    )
    rows = base.read_csv(csv_path, mirror=True)
    ratio = float(cfg["current_density_ratio"])
    calibration = sweep.calibration(rows, ratio)

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
        mismatches.append(100.0 * (a - b) / (0.5 * (a + b)))

    vdd = float(cfg["nominal_characterization_seed"]["vdd_v"])
    headroom = min(
        vdd - max(row["vgs_small_v"], row["vgs_large_v"])
        for row in rows
    )
    return {
        "seed": seed,
        "tag": tag,
        "dvgs_25c_v": by_temp[25.0]["dvgs_v"],
        "max_abs_branch_mismatch_pct": max(abs(x) for x in mismatches),
        "two_point_max_abs_error_c": calibration[
            "two_point_max_abs_error_c"
        ],
        "three_point_max_abs_error_c": max(abs(x) for x in quad_errors),
        "three_point_rms_error_c": math.sqrt(
            sum(x * x for x in quad_errors) / len(quad_errors)
        ),
        "min_headroom_v": headroom,
        "max_power_w": max(row["power_w"] for row in rows),
        "csv_path": str(csv_path.relative_to(ROOT)),
        "csv_sha256": base.sha256_file(csv_path),
        "deck_path": str(deck.relative_to(ROOT)),
        "deck_sha256": base.sha256_file(deck),
        "log_path": str(log.relative_to(ROOT)),
        "log_sha256": base.sha256_file(log),
    }


def write_summary(rows: list[dict]) -> None:
    with SUMMARY.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    cfg = deepcopy(base.load_requirements())
    design_hash = base.sha256_file(base.REQ)
    if design_hash != base.EXPECTED_REQ_SHA256:
        raise RuntimeError("design requirements hash mismatch")
    seed_cfg = cfg["nominal_characterization_seed"]
    seed_cfg["vdd_v"] = 1.2
    seed_cfg["reference_current_a"] = 1e-8

    model = base.locate_model()
    sections = base.library_sections(model)
    if "tt_mm" not in sections:
        raise RuntimeError("SKY130 model does not expose tt_mm")

    RAW.mkdir(parents=True, exist_ok=True)
    for old in RAW.glob("*"):
        if old.is_file():
            old.unlink()

    samples = []
    for index, seed in enumerate(SEEDS, start=1):
        sample = run_seed(model, cfg, seed, "sample")
        samples.append(sample)
        print(
            f"PASS mismatch {index:02d}/{len(SEEDS)} seed={seed} "
            f"mismatch={sample['max_abs_branch_mismatch_pct']:.3f}%",
            flush=True,
        )

    repeat = run_seed(model, cfg, REPEAT_SEED, "repeat")
    first = samples[0]
    repeat_fields = (
        "dvgs_25c_v",
        "max_abs_branch_mismatch_pct",
        "two_point_max_abs_error_c",
        "three_point_max_abs_error_c",
        "min_headroom_v",
        "max_power_w",
    )
    for field in repeat_fields:
        if not math.isclose(
            float(first[field]),
            float(repeat[field]),
            rel_tol=0.0,
            abs_tol=2e-6 if field == "dvgs_25c_v" else 1e-12,
        ):
            raise RuntimeError(f"seed repeatability failed for {field}")

    # Confirm the tt_mm section actually produced stochastic variation.
    dv25 = [float(row["dvgs_25c_v"]) for row in samples]
    if max(dv25) - min(dv25) < 1e-6:
        raise RuntimeError("tt_mm seeds produced no meaningful dVGS variation")

    write_summary(samples)
    mismatch = [float(row["max_abs_branch_mismatch_pct"]) for row in samples]
    two = [float(row["two_point_max_abs_error_c"]) for row in samples]
    three = [float(row["three_point_max_abs_error_c"]) for row in samples]

    aggregate = {
        "unique_samples": len(samples),
        "temperature_points_per_sample": len(base.TEMPS),
        "operating_points": len(samples) * len(base.TEMPS),
        "candidate_vdd_v": 1.2,
        "candidate_iref_a": 1e-8,
        "library_section": "tt_mm",
        "p50_max_abs_branch_mismatch_pct": percentile(mismatch, 0.50),
        "p95_max_abs_branch_mismatch_pct": percentile(mismatch, 0.95),
        "max_abs_branch_mismatch_pct": max(mismatch),
        "p95_two_point_max_abs_error_c": percentile(two, 0.95),
        "max_two_point_max_abs_error_c": max(two),
        "p95_three_point_max_abs_error_c": percentile(three, 0.95),
        "max_three_point_max_abs_error_c": max(three),
        "three_point_samples_le_0p5c": sum(x <= 0.5 for x in three),
        "repeat_seed": REPEAT_SEED,
        "repeatability_pass": True,
    }
    file_hashes = {}
    for row in samples + [repeat]:
        for kind in ("csv", "deck", "log"):
            path_key = f"{kind}_path"
            hash_key = f"{kind}_sha256"
            file_hashes[row[path_key]] = row[hash_key]
    file_hashes[str(SUMMARY.relative_to(ROOT))] = base.sha256_file(SUMMARY)

    manifest = {
        "status": "PASS",
        "evidence_class": (
            "Exploratory SKY130 tt_mm local-mismatch Monte Carlo; "
            "not foundry statistical signoff"
        ),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "design_requirements_sha256": design_hash,
        "ngspice_version": base.ngspice_version(),
        "model_path": str(model),
        "model_sha256": base.sha256_file(model),
        "pdk_sources": base.pdk_sources(model),
        "seed_list": SEEDS,
        "repeat_seed": REPEAT_SEED,
        "summary": {
            "path": str(SUMMARY.relative_to(ROOT)),
            "sha256": base.sha256_file(SUMMARY),
            "rows": len(samples),
        },
        "aggregate": aggregate,
        "files_sha256": file_hashes,
        "scope_note": (
            "40 deterministic local-mismatch samples at tt_mm on the "
            "selected 1.2 V / 10 nA mirror candidate. This is exploratory "
            "PDK mismatch evidence, not a yield or silicon-distribution claim."
        ),
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
