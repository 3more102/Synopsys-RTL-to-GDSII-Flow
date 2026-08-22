# MIPS_16 Professional ASIC RTL-to-GDSII Automation Flow

A Tcl-first Synopsys flow for **RTL → synthesis → equivalence → STA → floorplan → PG → placement → CTS → routing → extraction → signoff STA/power → conditional ECO → PV preparation → GDSII → deliverables**.

The repository intentionally separates **project settings**, **technology data**, and **flow methodology**. It does not guess proprietary SAED/foundry paths, routing layers, special cells, runsets, extraction models, DRC/LVS decks, or measured power values.

## Flow

```text
RTL -> RTL sanity -> DC synthesis -> Formality + pre-layout PrimeTime
 -> ICC2 init -> floorplan -> power plan -> placement -> pre-CTS -> CTS
 -> post-CTS opt -> route -> route_opt -> closure -> final netlist/SDF
 -> SPEF extraction -> PrimeTime signoff -> PrimeTime PX power
 -> optional ECO -> DRC/LVS/IR-EM preparation -> GDSII -> final delivery
```

## First configuration

1. Copy `.env.example` to `.env.local` and edit **only real machine/PDK values**. `.env.local` is ignored by Git, and `source setup.sh` loads it automatically.
2. Put Verilog/SystemVerilog under `rtl/`, or configure `RTL_FILELIST` for an external file list.
3. Configure at least the logical library and reference NDM before `make env`:

```bash
export TARGET_LIBRARY=/absolute/path/to/saed90nm_max_hvt.db
export STD_CELL_NDM=/absolute/path/to/saed90nm_hvt_mips.ndm
export TECH_FILE=/absolute/path/to/technology.tf        # optional if reference NDM embeds technology
export TLU_PLUS_MAX=/absolute/path/to/max.tluplus       # required for a qualified RC setup
export TLU_PLUS_MIN=/absolute/path/to/min.tluplus
export TLU_PLUS_MAP=/absolute/path/to/layer.map
export GDS_LAYER_MAP=/absolute/path/to/gdsout.map       # required before GDS stream-out
```

4. For PG creation, set actual PDK-valid layers. Do **not** copy layer names from another technology:

```bash
export PG_RING_H_LAYER=<actual layer>
export PG_RING_V_LAYER=<actual layer>
export PG_MESH_H_LAYER=<actual layer>
export PG_MESH_V_LAYER=<actual layer>
export PG_STD_CELL_RAIL_LAYER=<actual std-cell rail layer>
```

5. Review `config/project_config.tcl`: clock period, I/O delay, uncertainty, load, design-rule constraints, utilization, aspect ratio and core offset.
6. Review `constraints/*.sdc`. False paths/multicycle paths are deliberately absent until justified.

## Tool requirements

Required for the full default path:

- Synopsys Design Compiler / DC Ultra: synthesis and generic RTL structural sanity checks.
- Synopsys Formality: RTL-to-synth equivalence.
- Synopsys PrimeTime: pre/post-layout STA.
- Synopsys IC Compiler II: NDM physical implementation and stream-out.
- Python 3: report parsing and summaries.

Optional/licensed extensions:

- PrimeTime PX for richer power analysis.
- StarRC for golden parasitic extraction when native ICC2 SPEF export is not sufficient/available.
- IC Validator for foundry DRC/LVS.
- PrimeRail/RedHawk for IR-drop/EM.
- SpyGlass or equivalent for dedicated lint/CDC/RDC.
- TestMAX/DFT Compiler for scan/ATPG.

## Run commands

```bash
source setup.sh
```
Sets default executable names and `ASIC_PROJECT_ROOT`; environment variables remain overrideable.

```bash
make env
```
Checks RTL, SDC, target `.db`, NDM reference library, configured optional technology inputs, writable directories, and creates a PASS/UNKNOWN-aware environment record.

```bash
make lint
```
Analyzes/elaborates/links RTL in Design Compiler and emits structural reports. This is not a replacement for dedicated CDC/RDC.

```bash
make synth
```
Runs DC Ultra synthesis, applies SDC, writes mapped Verilog/DDC/SDC/SDF when supported, and emits timing/area/power/QoR reports.

```bash
make formal
```
Runs Formality reference RTL versus implementation netlist. The target fails with nonzero status when `verify` does not return equivalence.

```bash
make presta
```
Runs PrimeTime max/min analysis on the synthesized netlist before physical parasitics.

```bash
make init
```
Creates the ICC2 NDM design library, imports the synthesized netlist, links the block, and loads SDC.

```bash
make floorplan
```
Creates a utilization/aspect-ratio based floorplan (or explicit die boundary when enabled), reports physical/timing state, and saves the `floorplan` block.

```bash
make floorplan-screenshot
```
Optional GUI target. Opens the saved floorplan, zooms to fit, and writes `screenshots/MIPS_16_floorplan.png` when a valid `DISPLAY` and ICC2 GUI commands are available. It is deliberately not part of `make all` because headless runs may not have a display.

```bash
make powerplan
```
Connects PG nets and compiles pattern-based core ring, mesh, standard-cell rails and macro PG connections using only configured layer names. It intentionally fails when a required real PDK layer variable is empty.

```bash
make place
```
Runs ICC2 `place_opt`, legality, congestion and QoR checks.

```bash
make prects
```
Performs an incremental placement/optimization pass before clock tree synthesis.

```bash
make cts
```
Runs ICC2 `clock_opt`, then records clock/timing/QoR evidence.

```bash
make postcts
```
Runs post-CTS optimization with the implemented clock tree present.

```bash
make route
make postroute
make closure
```
Runs `route_auto`, `route_opt`, then bounded iterative post-route optimization. Closure is **not** declared only because the commands completed; parsed WNS/TNS/hold/route evidence must meet targets.

```bash
make outputs
make extract
```
Writes final routed netlist/SDF/SDC, then generates SPEF using ICC2 `write_parasitics` when supported. For an external golden extraction flow, configure a PDK-qualified StarRC command file and run `scripts/extraction/run_starrc.sh`; the repository never invents an extraction deck.

```bash
make signoff
```
Runs PrimeTime on final netlist + SDC + extracted SPEF with propagated clocks, setup/hold and constraint reports.

```bash
make power
```
Runs vectorless post-layout power estimation when the PrimeTime PX features are available. Results are explicitly labeled as estimates.

```bash
make eco
```
Optional conditional ECO path. It snapshots setup/hold metrics, runs routed optimization only when needed, compares before/after metrics, and promotes an ECO block only when it does not regress the opposite timing class.

```bash
make drc
make gds
make lvs
```
Runs ICC2 in-design route/PG checks, streams GDS using the configured layer map, and prepares LVS inputs/status. Foundry DRC/LVS remain `UNKNOWN` unless qualified decks are actually run.

```bash
make reports
make final
```
Builds CSV/JSON/Markdown QoR summaries and collects final deliverables/checksums/manifests.

```bash
make all
```
Builds the complete default flow. File-based stamps prevent already completed expensive stages from rerunning when their tracked inputs are unchanged.

## Optional analysis hooks

- `make saif-power` / `make vcd-power`: activity-based PrimeTime PX power when activity files are configured.
- `scripts/cdc/run_spyglass_cdc.sh` and `scripts/rdc/run_spyglass_rdc.sh`: dedicated SpyGlass wrappers requiring a reviewed project and installed methodology goal.
- `scripts/gls/run_vcs_gls.sh`: optional post-route gate-level timing simulation hook.
- `scripts/dft/`: scan/DFT integration template; disabled by default.
- `scripts/common/mmmc_setup.tcl`: real ICC2 mode/corner/scenario infrastructure; scenarios stay disabled until actual PVT library data is supplied.
- `make dse`: controlled PPA design-space sweep infrastructure; it is never launched by the default flow.

## Restart / resume

```bash
./run_flow.sh --resume placement
./run_flow.sh --resume cts
./run_flow.sh --to route
```

The runner uses Make targets and their checkpoint stamps. After changing a physical technology/floorplan input that invalidates the NDM database, use `make distclean` deliberately and rebuild; the flow never silently destroys a design library.

## Cleaning policy

```bash
make clean
```
Removes temporary `work/` contents only.

```bash
make clean-results
```
Removes reports, logs and the assembled `final_delivery/` package while deliberately preserving implementation databases/artifacts/checkpoints so resume stamps do not become stale.

```bash
make distclean
```
Deliberately removes generated implementation databases, checkpoints and generated artifacts in addition to reports. Source RTL, constraints, configuration and scripts are protected by path validation.

## Outputs

- `logs/`: timestamped tool logs.
- `reports/`: stage reports plus `reports/status/*.status`.
- `results/synthesis/`: mapped netlist, DDC, SDC, optional synthesis SDF/SVF.
- `database/`: ICC2 design library.
- `checkpoints/`: stage marker files plus active ECO block selection.
- `netlist/`: post-route Verilog.
- `spef/`, `extracted/`: parasitic exchange files.
- `sdf/`: timing back-annotation.
- `gds/`: GDSII.
- `final_delivery/`: collected delivery set, manifest, checksums and floorplan submission package.

## Debugging

Use `scripts/debug/` for setup, hold, clock, congestion, routing/PG DRC, fanout and transition/capacitance reports. These scripts are report-only and do not alter the design.

Common failure classes:

- **Unresolved RTL/library references**: inspect `reports/lint/check_design*.rpt` and `reports/synthesis/check_design*.rpt`.
- **Bad SDC / unconstrained paths**: inspect `check_timing.rpt`, clocks, exceptions and PrimeTime coverage.
- **ICC2 link failure**: check NDM attachment and mapped cell names.
- **PG failure**: verify actual layer names, PG pin patterns and the technology's via/layer rules.
- **Placement/routing failure**: inspect legality/congestion/check_routes and reduce utilization or repair floorplan constraints rather than blindly adding optimizations.
- **Signoff mismatch**: verify final netlist, exact SDC, SPEF annotation and library corner consistency.
- **GDS failure**: provide a valid layer map; no map is guessed.
- **DRC/LVS UNKNOWN**: configure and execute foundry-qualified runsets/decks.

See `docs/COMMANDS.md`, `docs/ASIC_FILE_FORMATS.md`, `docs/ASIC_FLOW_CHECKLIST.md`, and `docs/FILE_GUIDE.md`.
