# File Guide

This repository is organized so project intent, technology data, implementation methodology, generated evidence, and final deliverables remain separate.

## Root

- `README.md` — setup, tool requirements, stage commands, outputs, and debugging guidance.
- `Makefile` — dependency-aware RTL-to-GDSII stage orchestration.
- `setup.sh` — loads optional `.env.local`, exports tool command names, and sets `ASIC_PROJECT_ROOT`.
- `run_flow.sh` — sequential runner with single-stage, `--from`, `--to`, and `--resume` operation.
- `resume.sh` — convenience wrapper for resuming from one stage.
- `clean.sh` — guarded cleanup; source/config/constraints are protected.
- `.env.example` — machine/PDK configuration template. Copy to `.env.local`; never commit local proprietary paths or secrets.
- `.gitignore` — excludes EDA databases, logs, caches, generated GDS/OAS, and transient state.

## Configuration

- `config/project_config.tcl` — project name, top module, clock/I/O assumptions, floorplan knobs, output directories, and closure criteria.
- `config/technology.tcl` — NDM, TLU+, routing layers, PG geometry, special-cell lists, CTS layers, and optional extraction data. Unknown PDK values intentionally remain empty.
- `config/libraries.tcl` — target/link logical libraries and NDM reference library list.
- `config/rtl_files.tcl` — `.v`/`.sv` discovery, external file list, include directories, and defines.
- `config/flow_options.tcl` — methodology switches such as UPF, clock gating, StarRC, fillers, DFT, and effort levels.
- `config/physical_constraints.tcl` — explicit macro placement, halos, blockages, and pin constraints.
- `config/corners.tcl`, `modes.tcl`, `scenarios.tcl` — MMMC scaffolding; disabled until real corner libraries are supplied.

## Timing and power intent

- `constraints/top.sdc` — sources the complete constraint set.
- `constraints/clocks.sdc` — primary clocks, uncertainty, and clock transition.
- `constraints/io.sdc` — input/output delays, driving model/input transition, and output load.
- `constraints/design_constraints.sdc` — max transition, fanout, and capacitance limits.
- `constraints/timing_exceptions.sdc` — deliberately empty templates; exceptions require architectural justification.
- `power_intent/top.upf` — inactive IEEE 1801 template; no power domains are invented.

## Common infrastructure

`scripts/common/` contains configuration loading, file/tool validation, RTL reading, MMMC setup, path groups, status/report utilities, reproducibility manifests, run snapshots, stage launch wrappers, and ECO downstream invalidation.

Important files:
- `common_procs.tcl` — shared Tcl error handling, reporting, status, checkpoint, and filesystem helpers.
- `check_environment.tcl` — validates required RTL/SDC/library/NDM inputs and reports optional PDK gaps.
- `read_rtl.tcl` — consistent Verilog/SystemVerilog preprocessing and elaboration for synthesis.
- `run_stage.sh` — executes a tool stage with metadata and `pipefail` logging.

## Front-end stages

- `scripts/lint/` — DC-based structural RTL sanity plus optional SpyGlass template.
- `scripts/synthesis/01_synthesis.tcl` — Design Compiler mapping, path groups, QoR/timing/area/power reports, SVF, Verilog, DDC, SDC, and optional SDF.
- `scripts/formal/` — Formality RTL-vs-synthesis equivalence with SystemVerilog-aware reading, matching, and failure evidence.
- `scripts/sta/01_prelayout_sta.tcl` — PrimeTime pre-layout max/min STA and timing audits.
- `scripts/cdc/`, `scripts/rdc/` — dedicated SpyGlass hooks; synthesis/STA is not treated as CDC/RDC signoff.
- `scripts/dft/` — optional scan/DFT integration template.

## Physical implementation

- `scripts/floorplan/00_create_design_lib.tcl` — ICC2 NDM design library creation, netlist link, SDC, UPF hook, and TLU+ setup.
- `scripts/floorplan/01_floorplan.tcl` — utilization/explicit-die floorplan, macro placement/halos, blockages, and pin planning.
- `scripts/floorplan/02_gui_screenshot_helper.tcl` — optional real ICC2 GUI screenshot capture.
- `scripts/floorplan/03_physical_only_cells.tcl` — configured tap/endcap insertion.
- `scripts/powerplan/01_powerplan.tcl` — PG logical connection, ring, mesh, standard-cell rails, macro PG, and checks.
- `scripts/placement/` — placement, legality/congestion checks, pre-CTS optimization, spares, and tie cells.
- `scripts/cts/` — CTS setup, optional clock-cell/NDR/layer policy, `clock_opt`, and post-CTS optimization.
- `scripts/routing/` — route, route optimization, post-route checks, and bounded iterative timing closure.

## Extraction, signoff, power, and ECO

- `scripts/extraction/` — ICC2 SPEF writing and external StarRC handoff template/wrapper.
- `scripts/signoff/01_postroute_sta.tcl` — PrimeTime extracted STA with propagated clocks, setup/hold, path groups, and exception/coverage audits.
- `scripts/power/` — vectorless, SAIF, and VCD PrimeTime PX flows. Reports identify analysis method and never claim measured silicon power.
- `scripts/eco/` — report-driven setup/hold/route ECO candidates with before/after measurement and non-regression checks.
- `scripts/debug/` — report-only setup, hold, clock, congestion, fanout, reset, transition/capacitance, DRC, and special-cell discovery helpers.

## Physical verification and final outputs

- `scripts/physical_verification/` — ICC2 route/PG evidence plus DRC/LVS/IR-EM preparation. Foundry signoff remains `UNKNOWN` without qualified decks/models.
- `scripts/final/00_write_outputs.tcl` — final routed netlist, SDF, and SDC.
- `scripts/final/01_write_gds.tcl` — GDSII stream-out requiring an explicit PDK layer map.
- `scripts/final/02_insert_fillers.tcl` — optional configured filler/decap insertion.
- `scripts/final/collect_deliverables.sh` — final package, status manifest, reports, and SHA-256 checksums.

## Python reporting

`python/` parses timing, QoR, area, power, and congestion reports; evaluates setup/hold status; creates CSV/JSON/Markdown summaries; compares runs; tracks QoR trends; and generates `FINAL_SUMMARY.md`. Missing evidence is represented as `N/A`/`UNKNOWN`, never fabricated.

## Optional workflows

- `scripts/dse/` — prepares isolated utilization/aspect-ratio/clock-period experiments; no large sweep runs automatically.
- `scripts/gls/` — VCS gate-level simulation hook using the final netlist/SDF and user-provided testbench/library models.

## Source and technology placeholders

- `rtl/` — project RTL input.
- `lib/` and `tech/` — documentation/placeholders only. Proprietary PDK/library files should normally stay outside Git and be referenced through environment variables.

## Generated directories

`work/`, `logs/`, `reports/`, `results/`, `checkpoints/`, `database/`, `extracted/`, `netlist/`, `spef/`, `sdf/`, `gds/`, `saif/`, `screenshots/`, `runs/`, and `final_delivery/` are generated or populated by the flow. Large/transient artifacts are ignored where appropriate.

For command-level detail see `docs/COMMANDS.md`; for file-format semantics see `docs/ASIC_FILE_FORMATS.md`; for signoff readiness see `docs/ASIC_FLOW_CHECKLIST.md`.
