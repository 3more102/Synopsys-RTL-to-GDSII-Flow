#!/usr/bin/env python3
"""Screen PTAT mirror local-mismatch sensitivity versus reference current.

Uses the same deterministic SKY130 ``tt_mm`` seeds at each current so current
is the only intentional experiment variable.  This remains exploratory PDK
mismatch evidence, not foundry statistical signoff or a silicon-yield claim.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import csv
import json
from pathlib import Path

import run_local_mismatch_mc_ci as mc
import run_sky130_ci as base

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
SUMMARY = RESULTS / "sky130_mismatch_bias_screen.csv"
MANIFEST = RESULTS / "sky130_mismatch_bias_screen_manifest.json"

VDD_V = 1.2
CURRENTS_A = (10e-9, 30e-9, 100e-9, 300e-9)
SEEDS = mc.SEEDS[:20]


def percentile(values: list[float], q: float) -> float:
    return mc.percentile(values, q)


def main() -> int:
    cfg0 = base.load_requirements()
    design_hash = base.sha256_file(base.REQ)
    if design_hash != base.EXPECTED_REQ_SHA256:
        raise RuntimeError("design requirements hash mismatch")

    model = base.locate_model()
    sections = base.library_sections(model)
    if "tt_mm" not in sections:
        raise RuntimeError("SKY130 model does not expose tt_mm")

    samples: list[dict] = []
    aggregates: list[dict] = []
    for current in CURRENTS_A:
        cfg = deepcopy(cfg0)
        seed_cfg = cfg["nominal_characterization_seed"]
        seed_cfg["vdd_v"] = VDD_V
        seed_cfg["reference_current_a"] = current
        current_na = int(round(current * 1e9))
        current_rows: list[dict] = []
        for index, seed in enumerate(SEEDS, start=1):
            row = mc.run_seed(
                model,
                cfg,
                seed,
                f"screen_{current_na}n",
            )
            row["vdd_v"] = VDD_V
            row["iref_a"] = current
            current_rows.append(row)
            samples.append(row)
            print(
                f"PASS screen IREF={current_na} nA "
                f"{index:02d}/{len(SEEDS)} seed={seed} "
                f"mismatch={row['max_abs_branch_mismatch_pct']:.3f}% "
                f"3pt={row['three_point_max_abs_error_c']:.3f} C",
                flush=True,
            )

        mismatch = [
            float(row["max_abs_branch_mismatch_pct"])
            for row in current_rows
        ]
        two = [
            float(row["two_point_max_abs_error_c"])
            for row in current_rows
        ]
        three = [
            float(row["three_point_max_abs_error_c"])
            for row in current_rows
        ]
        power = [float(row["max_power_w"]) for row in current_rows]
        headroom = [float(row["min_headroom_v"]) for row in current_rows]
        aggregates.append({
            "vdd_v": VDD_V,
            "iref_a": current,
            "samples": len(current_rows),
            "p50_mismatch_pct": percentile(mismatch, 0.50),
            "p95_mismatch_pct": percentile(mismatch, 0.95),
            "max_mismatch_pct": max(mismatch),
            "p50_two_point_max_error_c": percentile(two, 0.50),
            "p95_two_point_max_error_c": percentile(two, 0.95),
            "max_two_point_max_error_c": max(two),
            "p50_three_point_max_error_c": percentile(three, 0.50),
            "p95_three_point_max_error_c": percentile(three, 0.95),
            "max_three_point_max_error_c": max(three),
            "three_point_samples_le_0p5c": sum(x <= 0.5 for x in three),
            "max_power_w": max(power),
            "min_headroom_v": min(headroom),
        })

    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(aggregates[0].keys()))
        writer.writeheader()
        writer.writerows(aggregates)

    files_sha256: dict[str, str] = {
        str(SUMMARY.relative_to(ROOT)): base.sha256_file(SUMMARY)
    }
    for row in samples:
        for kind in ("csv", "deck", "log"):
            path_key = f"{kind}_path"
            hash_key = f"{kind}_sha256"
            files_sha256[row[path_key]] = row[hash_key]

    manifest = {
        "status": "PASS",
        "evidence_class": (
            "Exploratory SKY130 tt_mm mismatch-vs-bias screen; "
            "not foundry statistical signoff"
        ),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "design_requirements_sha256": design_hash,
        "ngspice_version": base.ngspice_version(),
        "model_sha256": base.sha256_file(model),
        "pdk_sources": base.pdk_sources(model),
        "library_section": "tt_mm",
        "vdd_v": VDD_V,
        "currents_a": list(CURRENTS_A),
        "seed_list": list(SEEDS),
        "shared_seed_count": len(SEEDS),
        "operating_points": len(samples) * len(base.TEMPS),
        "summary": {
            "path": str(SUMMARY.relative_to(ROOT)),
            "sha256": base.sha256_file(SUMMARY),
            "rows": len(aggregates),
        },
        "aggregates": aggregates,
        "files_sha256": files_sha256,
        "scope_note": (
            "Twenty identical deterministic tt_mm seeds are applied at each "
            "of four reference currents. This is an operating-point screen, "
            "not a foundry-qualified statistical or yield study."
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
