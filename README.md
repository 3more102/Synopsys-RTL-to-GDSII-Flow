# Synopsys RTL-to-GDSII Flow

A reusable Tcl-first ASIC implementation framework for **RTL → synthesis → formal equivalence → STA → floorplan → power planning → placement → CTS → routing → extraction → signoff → power → ECO → physical-verification preparation → GDSII**.

The default example project is `MIPS_16`, but project, technology, constraints, libraries, special cells, routing layers and signoff decks are isolated from the methodology. The repository deliberately does **not** invent PDK-specific values or claim signoff checks that were not actually executed.

## Core architecture

```text
RTL / SystemVerilog
       |
       v
Static repository + SDC audit
       |
       v
Environment / tool capability validation
       |
       v
Design Compiler synthesis
       |-------------------|
       v                   v
Formality               PrimeTime pre-STA
       |                   |
       +---------+---------+
                 |
                 v
ICC2 init -> floorplan -> PG -> placement -> pre-CTS -> CTS
                 |
                 v
post-CTS -> route -> route_opt -> timing closure
                 |
                 v
final netlist/SDF -> extraction -> PrimeTime signoff -> power
                 |
                 v
conditional measured ECO -> DRC/LVS/IR-EM preparation -> GDSII
                 |
                 v
release contract + QoR regression gate + reproducible snapshot
```

## Engineering controls

The repository contains several controls that are intentionally separate from normal tool success/failure:

- **Per-stage process locking** prevents concurrent writers from corrupting the same design state.
- **Runtime JSON evidence** records tool path, script, Git SHA, dirty state, runtime and exit code for every launched stage.
- **Input fingerprints** detect stale checkpoints when RTL/config/environment/PDK/tool identity changes even if GNU Make timestamps do not.
- **Static SDC audit** detects broad timing exceptions and suspicious multicycle usage before an expensive run begins.
- **Synopsys capability probe** checks whether the installed release exposes required commands without loading or modifying a design.
- **Release verification contract** checks required artifacts and report-derived PASS/FAIL evidence instead of equating `exit 0` with signoff.
- **QoR regression gate** compares a new run against an explicit known-good baseline using a reviewable policy.
- **Measured ECO acceptance** compares before/after timing instead of assuming an ECO improved QoR.
- **GitHub Actions CI** runs license-free syntax/config/unit/SDC checks. It is not a substitute for licensed Synopsys or foundry signoff.

## First setup

```bash
cp .env.example .env.local
```

Edit only real local/PDK values in `.env.local`, for example:

```bash
export TARGET_LIBRARY=/absolute/path/to/saed90nm_max_hvt.db
export STD_CELL_NDM=/absolute/path/to/saed90nm_hvt_mips.ndm
export TECH_FILE=/absolute/path/to/technology.tf
export TLU_PLUS_MAX=/absolute/path/to/max.tluplus
export TLU_PLUS_MIN=/absolute/path/to/min.tluplus
export TLU_PLUS_MAP=/absolute/path/to/layer.map
export GDS_LAYER_MAP=/absolute/path/to/gdsout.map
```

For power-grid construction, supply only PDK-valid layer names:

```bash
export PG_RING_H_LAYER=<actual layer>
export PG_RING_V_LAYER=<actual layer>
export PG_MESH_H_LAYER=<actual layer>
export PG_MESH_V_LAYER=<actual layer>
export PG_STD_CELL_RAIL_LAYER=<actual layer>
```

Then:

```bash
source setup.sh
make doctor
make env
```

`make doctor` is the preferred pre-run check. It executes repository/config/unit/SDC checks and an advisory capability probe. Missing Synopsys tools are reported as `UNKNOWN` unless `REQUIRE_TOOL_CAPABILITIES=1` is requested.

## Main flow commands

```bash
make lint
make synth
make formal
make presta
make init
make floorplan
make powerplan
make place
make prects
make cts
make postcts
make route
make postroute
make closure
make outputs
make extract
make signoff
make power
make drc
make gds
make lvs
make reports
make final
make verify
```

Or execute the default dependency chain:

```bash
make all
```

The framework keeps formal and pre-layout STA as separate evidence paths and does not mark timing closed just because implementation commands completed.

## Freshness-aware resume

Every successful policy-covered stage stores a fingerprint under `checkpoints/fingerprints/`. The fingerprint includes repository content hashes plus configured environment, external PDK/library identity and resolved tool executable identity.

```bash
make fingerprint STAGE=synth
make freshness STAGE=synth
make freshness STAGE=synth DETAILS=1
```

`run_flow.sh` checks freshness before reusing an existing checkpoint that Make considers current:

```bash
./run_flow.sh --resume synth --to floorplan
```

If the checkpoint was produced with different tracked inputs, the runner stops rather than silently reusing it. `FLOW_FRESHNESS_CHECK=0` is an explicit bypass for expert/debug use only.

## SDC safety audit

```bash
make sdc-audit
```

The static audit reports global false paths, broad wildcard timing exceptions, false-pathing all registers, malformed async clock grouping, disabled timing arcs, case analysis, suspicious multicycle setup/hold pairing and missing active `create_clock`. Results are stored under `reports/audit/`.

This is a heuristic preflight review only. Real timing signoff must still use tool-native `check_timing`, timing coverage, exception reports and path review.

## Tool-release capability probe

```bash
make capabilities
REQUIRE_TOOL_CAPABILITIES=1 make capabilities
```

For each installed `dc_shell`, `icc2_shell`, `pt_shell` and `fm_shell`, a read-only Tcl probe checks configured command availability with `info commands`; it does not execute the commands or load a design. Reports are written to `reports/capabilities/`.

- tool not installed: `UNKNOWN` by default;
- installed tool missing a required configured command: `FAIL`;
- all required configured commands visible: `PASS`.

The required/optional command policy is in `config/tool_capabilities.json`.

## QoR regression gate

After a known-good implementation, archive its `reports/summary/qor_summary.json`, then compare future runs:

```bash
QOR_BASELINE=/path/to/golden/qor_summary.json make qor-gate
```

Policy is stored in `config/qor_policy.json`. Signoff timing can be a hard gate while PPA/runtime metrics can be warnings or hard failures according to project policy. Missing required evidence fails rather than becoming an implicit pass.

## Release verification

```bash
make verify
REQUIRE_SDF=1 make verify
STRICT_SIGNOFF=1 make verify
```

The release contract in `config/stage_contracts.json` verifies final netlist, SDC, SPEF, GDS and required status evidence. `STRICT_SIGNOFF=1` requires DRC/LVS PASS evidence; without actual foundry-qualified runs those statuses remain `UNKNOWN` by design.

```bash
make release
```

Collects the final package, verifies the release contract and records a reproducible snapshot.

## Tools

Required for the complete default flow:

- Synopsys Design Compiler / DC Ultra
- Synopsys Formality
- Synopsys PrimeTime
- Synopsys IC Compiler II
- Python 3

Optional integrations include PrimeTime PX, StarRC, IC Validator, PrimeRail/RedHawk, SpyGlass/equivalent CDC-RDC tools and DFT/TestMAX flows. Optional integrations remain `UNKNOWN` until real licensed tools/decks are supplied.

## Important outputs

```text
logs/                         durable tool logs
reports/runtime/              per-stage runtime JSON
reports/status/               engineering and runner status records
reports/audit/                static SDC audit
reports/capabilities/         release compatibility probe
reports/summary/              QoR CSV/JSON/Markdown
checkpoints/fingerprints/     stage input fingerprints
results/synthesis/            mapped netlist/DDC/SDC/SDF where supported
database/                     ICC2 design library
netlist/                      final post-route Verilog
spef/                         extracted parasitics
sdf/                          timing back-annotation
gds/                          GDSII
final_delivery/               manifest, checksums and collected release set
```

## Clean and rebuild semantics

```bash
make clean
```
Removes temporary work content only.

```bash
make clean-results
```
Removes reports/logs/final package while preserving implementation state.

```bash
make distclean
```
Deliberately removes generated implementation databases/checkpoints/artifacts. Source RTL, constraints, configuration and scripts remain protected.

## Documentation

- `docs/COMMANDS.md` — command/tool reference.
- `docs/ASIC_FILE_FORMATS.md` — Verilog/SDC/SDF/SPEF/NDM/GDS and related formats.
- `docs/ASIC_FLOW_CHECKLIST.md` — stage-by-stage engineering checklist.
- `docs/FRESHNESS_CONSTRAINTS_AND_COMPATIBILITY.md` — input fingerprints, SDC audit and release compatibility probe.
- `docs/FILE_GUIDE.md` — repository layout.

## Signoff boundary

GitHub CI validates source/config/parser logic without proprietary licenses. A real tapeout claim additionally requires the correct PDK, corners, extraction models, activity assumptions, foundry-qualified DRC/LVS decks, and signoff execution on the licensed tool versions used by the project. The framework records `UNKNOWN` rather than fabricating success when that evidence is absent.
