#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
REQ = ROOT / "design_requirements.json"
TEMPS = [-40, -20, 0, 25, 50, 75, 100, 125]
CORNERS = ("tt", "ff", "ss")
K_B_OVER_Q = 8.617333262145e-5
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
    candidates = list(
        pdk_root.glob(
            "sky130/versions/*/sky130A/libs.tech/ngspice/sky130.lib.spice"
        )
    )
    candidates += list(
        pdk_root.glob(
            "versions/*/sky130A/libs.tech/ngspice/sky130.lib.spice"
        )
    )
    candidates += list(
        pdk_root.glob("**/sky130A/libs.tech/ngspice/sky130.lib.spice")
    )
    files = [p.resolve() for p in candidates if p.is_file()]
    if not files:
        raise FileNotFoundError(
            f"SKY130 ngspice model not found below {pdk_root}"
        )
    return sorted(set(files), key=str)[-1]


def library_sections(model: Path) -> set[str]:
    sections: set[str] = set()
    pattern = re.compile(r"^\s*\.lib\s+(\S+)", re.IGNORECASE)
    for line in model.read_text(
        encoding="utf-8", errors="ignore"
    ).splitlines():
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
    return (proc.stdout or proc.stderr).splitlines()[0].strip()


def ideal_deck(model: Path, corner: str, cfg: dict, csv_name: str) -> str:
    seed = cfg["nominal_characterization_seed"]
    nmos = seed["sensor_nmos"]
    return f'''* CI-only SKY130 PTAT ideal-bias characterization
.lib "{model}" {corner}
.param VDDVAL={seed["vdd_v"]:.12g}
.param IBIAS={seed["branch_current_a"]:.12g}
.param LCH={nmos["l_um"]:.12g}u
.param W1={nmos["w_small_um"]:.12g}u
.param W2={nmos["w_large_um"]:.12g}u
.param PTEMP=-40
.temp {{PTEMP}}
VDD vdd 0 DC {{VDDVAL}}
I1 vdd v1 DC {{IBIAS}}
I2 vdd v2 DC {{IBIAS}}
X1 v1 v1 0 0 sky130_fd_pr__nfet_01v8 L={{LCH}} W={{W1}}
X2 v2 v2 0 0 sky130_fd_pr__nfet_01v8 L={{LCH}} W={{W2}}
.control
set noaskquit
echo "temp_c,vgs_small_v,vgs_large_v,dvgs_v,supply_current_a,power_w" > {RESULTS / csv_name}
foreach t -40 -20 0 25 50 75 100 125
  alterparam PTEMP = $t
  reset
  op
  let dvgs = v(v1)-v(v2)
  let isupply = -i(VDD)
  let psupply = v(vdd)*isupply
  echo $t',' $&v(v1)',' $&v(v2)',' $&dvgs',' $&isupply',' $&psupply >> {RESULTS / csv_name}
end
quit
.endc
.end
'''


def mirror_deck(model: Path, corner: str, cfg: dict, csv_name: str) -> str:
    seed = cfg["nominal_characterization_seed"]
    nmos = seed["sensor_nmos"]
    pmos = seed["mirror_pmos"]
    return f'''* CI-only SKY130 PTAT PMOS-mirror characterization
.lib "{model}" {corner}
.param VDDVAL={seed["vdd_v"]:.12g}
.param IREF={seed["reference_current_a"]:.12g}
.param LNS={nmos["l_um"]:.12g}u
.param WNS1={nmos["w_small_um"]:.12g}u
.param WNS2={nmos["w_large_um"]:.12g}u
.param LPM={pmos["l_um"]:.12g}u
.param WPM={pmos["w_um"]:.12g}u
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
echo "temp_c,vgs_small_v,vgs_large_v,dvgs_v,supply_current_a,power_w,branch_small_a,branch_large_a" > {RESULTS / csv_name}
foreach t -40 -20 0 25 50 75 100 125
  alterparam PTEMP = $t
  reset
  op
  let dvgs = v(v1)-v(v2)
  let isupply = -i(VDD)
  let psupply = v(vdd)*isupply
  let ibranch1 = abs(i(VPROBE1))
  let ibranch2 = abs(i(VPROBE2))
  echo $t',' $&v(v1)',' $&v(v2)',' $&dvgs',' $&isupply',' $&psupply',' $&ibranch1',' $&ibranch2 >> {RESULTS / csv_name}
end
quit
.endc
.end
'''


def run_deck(text: str, stem: str) -> tuple[Path, Path]:
    deck = ROOT / f"{stem}.spice"
    log = RESULTS / f"{stem}.log"
    deck.write_text(text, encoding="utf-8")
    subprocess.run(
        ["ngspice", "-b", "-o", str(log), str(deck)],
        cwd=ROOT,
        check=True,
    )
    return deck, log


def read_csv(path: Path, mirror: bool = False) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, skipinitialspace=True)
        for raw in reader:
            row = {
                key.strip(): float(value.strip())
                for key, value in raw.items()
                if key is not None and value is not None
            }
            rows.append(row)
    if len(rows) != len(TEMPS):
        raise RuntimeError(
            f"{path}: expected {len(TEMPS)} rows, got {len(rows)}"
        )
    got_temps = [round(row["temp_c"]) for row in rows]
    if got_temps != TEMPS:
        raise RuntimeError(
            f"{path}: temperature grid mismatch: {got_temps}"
        )
    for row in rows:
        if not all(math.isfinite(value) for value in row.values()):
            raise RuntimeError(f"{path}: non-finite value")
        expected_dvgs = row["vgs_small_v"] - row["vgs_large_v"]
        if abs(expected_dvgs - row["dvgs_v"]) > 1e-7:
            raise RuntimeError(f"{path}: inconsistent dvgs")
        if row["supply_current_a"] <= 0 or row["power_w"] <= 0:
            raise RuntimeError(
                f"{path}: non-positive supply current or power"
            )
        if mirror:
            if (
                row["branch_small_a"] <= 0
                or row["branch_large_a"] <= 0
            ):
                raise RuntimeError(
                    f"{path}: non-positive mirror branch current"
                )
    return rows


def fit_metrics(
    rows: list[dict[str, float]], cfg: dict, mirror: bool = False
) -> dict:
    xs = [row["temp_c"] for row in rows]
    ys = [row["dvgs_v"] for row in rows]
    xbar = sum(xs) / len(xs)
    ybar = sum(ys) / len(ys)
    denom = sum((x - xbar) ** 2 for x in xs)
    slope = sum(
        (x - xbar) * (y - ybar) for x, y in zip(xs, ys)
    ) / denom
    intercept = ybar - slope * xbar
    if slope <= 0:
        raise RuntimeError(f"non-PTAT slope {slope}")
    residuals = [
        y - (slope * x + intercept) for x, y in zip(xs, ys)
    ]
    temp_residuals = [residual / slope for residual in residuals]
    ratio = float(cfg["current_density_ratio"])
    n_eff = slope / (K_B_OVER_Q * math.log(ratio))
    t25 = next(row for row in rows if round(row["temp_c"]) == 25)
    vdd = float(cfg["nominal_characterization_seed"]["vdd_v"])
    guard = float(cfg["headroom_guardband_v_min"])
    min_headroom = min(
        vdd - max(row["vgs_small_v"], row["vgs_large_v"])
        for row in rows
    )
    result = {
        "ptat_slope_uv_per_k": slope * 1e6,
        "dvgs_25c_mv": t25["dvgs_v"] * 1e3,
        "effective_n": n_eff,
        "max_abs_nonlinearity_c": max(
            abs(value) for value in temp_residuals
        ),
        "max_power_uw": max(row["power_w"] for row in rows) * 1e6,
        "min_sensor_headroom_v": min_headroom,
        "headroom_pass": min_headroom >= guard,
    }
    if mirror:
        mismatches = []
        tracking = []
        iref = float(
            cfg["nominal_characterization_seed"]["reference_current_a"]
        )
        for row in rows:
            mean_i = 0.5 * (
                row["branch_small_a"] + row["branch_large_a"]
            )
            mismatch = (
                abs(row["branch_small_a"] - row["branch_large_a"])
                / mean_i
                * 100.0
            )
            mismatches.append(mismatch)
            tracking.append(abs(mean_i - iref) / iref * 100.0)
        result["max_branch_mismatch_percent"] = max(mismatches)
        result["max_reference_tracking_error_percent"] = max(tracking)
    return result


def pdk_sources(model: Path) -> str | None:
    pdk_root = Path(
        os.environ.get("PDK_ROOT", "/home/runner/pdk")
    ).expanduser()
    source = pdk_root / "sky130A" / "SOURCES"
    if source.is_file():
        return source.read_text(
            encoding="utf-8", errors="ignore"
        ).strip()
    for parent in model.parents:
        source = parent / "SOURCES"
        if source.is_file():
            return source.read_text(
                encoding="utf-8", errors="ignore"
            ).strip()
    return None


def main() -> int:
    cfg = load_requirements()
    design_hash = sha256_file(REQ)
    if design_hash != EXPECTED_REQ_SHA256:
        raise RuntimeError(
            "design_requirements.json hash does not match v12 release"
        )
    model = locate_model()
    sections = library_sections(model)
    missing = [corner for corner in CORNERS if corner not in sections]
    if missing:
        raise RuntimeError(
            f"model missing sections {missing}; found {sorted(sections)}"
        )

    summary: dict[str, dict] = {"ideal": {}, "mirror": {}}
    files: dict[str, str] = {}
    for architecture in ("ideal", "mirror"):
        for corner in CORNERS:
            stem = f"ptat_{architecture}_{corner}"
            csv_name = f"{stem}.csv"
            if architecture == "ideal":
                text = ideal_deck(model, corner, cfg, csv_name)
            else:
                text = mirror_deck(model, corner, cfg, csv_name)
            deck, log = run_deck(text, stem)
            csv_path = RESULTS / csv_name
            if not csv_path.is_file():
                raise RuntimeError(
                    f"ngspice did not create {csv_path}"
                )
            rows = read_csv(
                csv_path, mirror=(architecture == "mirror")
            )
            summary[architecture][corner] = fit_metrics(
                rows,
                cfg,
                mirror=(architecture == "mirror"),
            )
            for path in (deck, log, csv_path):
                files[str(path.relative_to(ROOT))] = sha256_file(path)
            print(
                f"PASS {architecture} {corner}: "
                f"{summary[architecture][corner]}"
            )

    manifest = {
        "status": "PASS",
        "evidence_class": (
            "real SKY130/open_pdks ngspice CI characterization"
        ),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "design_requirements_sha256": design_hash,
        "design_requirements_expected_sha256": EXPECTED_REQ_SHA256,
        "design_hash_match": True,
        "ngspice_version": ngspice_version(),
        "model_path": str(model),
        "model_sha256": sha256_file(model),
        "model_library_sections": sorted(sections),
        "pdk_sources": pdk_sources(model),
        "pdk_root": os.environ.get("PDK_ROOT"),
        "corners": list(CORNERS),
        "summary": summary,
        "files_sha256": files,
    }
    output = RESULTS / "sky130_ci_manifest.json"
    output.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
