# Synopsys RTL-to-GDSII Flow

A configurable, evidence-driven ASIC implementation framework for:

**RTL → synthesis → formal equivalence → pre-layout STA → floorplan → power planning → placement → CTS → routing → extraction → signoff STA/power → ECO → physical-verification preparation → GDSII → final delivery**

The default example project is `MIPS_16`, but the flow is structured so project settings, technology data, and methodology remain separate.

> This repository does **not** fabricate PDK paths, metal layers, special-cell names, foundry decks, timing results, power values, DRC/LVS results, or tapeout readiness. Unknown evidence remains `UNKNOWN` or causes an explicit failure when required by policy.

## Tool stack

Core flow:

- Synopsys Design Compiler / DC Ultra
- Synopsys Formality
- Synopsys PrimeTime
- Synopsys IC Compiler II
- Python 3

Optional integrations:

- PrimeTime PX
- StarRC
- IC Validator
- PrimeRail / RedHawk handoff
- SpyGlass CDC/RDC hooks
- VCS gate-level simulation hooks
- DFT/TestMAX integration templates

## Architecture

```text
RTL
 │
 ├─ RTL sanity / lint hooks
 │
 ├─ Design Compiler synthesis
 │     └─ mapped Verilog / DDC / SDC / reports
 │
 ├─ Formality equivalence
 ├─ PrimeTime pre-layout STA
 │
 └─ ICC2
       ├─ NDM design initialization
       ├─ floorplan
       ├─ tap/endcap hooks
       ├─ power ring / mesh / rails / macro PG
       ├─ placement
       ├─ spare/tie-cell hooks
       ├─ pre-CTS optimization
       ├─ CTS
       ├─ post-CTS optimization
       ├─ routing
       ├─ route optimization
       ├─ iterative closure
       ├─ filler/decap hooks
       └─ final netlist / SDF / GDS
              │
              ├─ parasitic extraction / StarRC handoff
              ├─ PrimeTime extracted signoff
              ├─ PrimeTime PX power
              ├─ measured ECO acceptance/rejection
              └─ final deliverables + manifests + checksums
```

## First setup

```bash
cp .env.example .env.local
source setup.sh
```

Set only real machine/PDK values, for example:

```bash
export TARGET_LIBRARY=/real/path/saed90nm_max_hvt.db
export STD_CELL_NDM=/real/path/saed90nm_hvt_mips.ndm
export TECH_FILE=/real/path/technology.tf
export TLU_PLUS_MAX=/real/path/max.tluplus
export TLU_PLUS_MIN=/real/path/min.tluplus
export TLU_PLUS_MAP=/real/path/layer.map
export GDS_LAYER_MAP=/real/path/gdsout.map
```

Power-grid layer names are intentionally not guessed:

```bash
export PG_RING_H_LAYER=<real layer>
export PG_RING_V_LAYER=<real layer>
export PG_MESH_H_LAYER=<real layer>
export PG_MESH_V_LAYER=<real layer>
export PG_STD_CELL_RAIL_LAYER=<real layer>
```

Then validate configuration before consuming EDA licenses:

```bash
make static
make config-check
```

`make static` performs license-free Bash, Python, JSON, Tcl/SDC, Makefile, configuration, and unit-test validation. GitHub Actions runs the same static validation on pushes and pull requests.

## Main flow

```bash
make env
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
```

Or:

```bash
make all
```

The Makefile uses stage stamps so completed expensive stages are not rerun when tracked inputs are unchanged.

## Flow runner

```bash
./run_flow.sh --list
./run_flow.sh --from placement --to route
./run_flow.sh --resume cts
./run_flow.sh --from route --to signoff --dry-run
```

Every invocation receives a `FLOW_RUN_ID`. Each EDA stage is protected by a per-stage lock to reduce accidental concurrent database writers.

The stage launcher writes:

```text
reports/runtime/<stage>_<timestamp>.json
reports/runtime/<stage>.latest.json
reports/status/<stage>_runner.status
```

Runtime evidence includes the executable path, Tcl script, Git commit/dirty state, start/end time, duration, log path, and process exit code.

A runner `PASS` only proves the tool process returned successfully. It does **not** override engineering timing/formal/physical status.

## Quality gates

### 1. Static validation

```bash
make static
```

Includes parser unit tests and license-free configuration sanity checks.

### 2. Release verification

```bash
make verify
```

The machine-readable contract in `config/stage_contracts.json` checks required final artifacts and evidence such as:

- post-route netlist
- final SDC
- SPEF
- GDS
- synthesis status
- Formality equivalence
- extraction status
- setup STA
- hold STA
- GDS generation

To require SDF too:

```bash
REQUIRE_SDF=1 make verify
```

To require qualified DRC/LVS `PASS` evidence:

```bash
STRICT_SIGNOFF=1 make verify
```

`FLOW_RELEASE PASS` is deliberately **not** synonymous with foundry tapeout signoff. `STRICT_SIGNOFF=1` should fail until real qualified DRC/LVS integrations produce valid evidence.

### 3. QoR regression gate

After saving a known-good QoR summary:

```bash
QOR_BASELINE=/path/to/golden/qor_summary.json make qor-gate
```

The policy is explicit in `config/qor_policy.json`.

Default behavior includes:

- signoff WNS must remain non-negative and not regress
- signoff TNS must remain non-negative and not regress
- worst hold slack must remain non-negative and not regress
- post-route timing regressions are detected when metrics exist
- optional area/power/congestion/runtime growth is reported according to configured policy
- missing required evidence fails; optional missing metrics become `SKIP`, never zero

Outputs:

```text
reports/summary/qor_regression.json
reports/summary/qor_regression.md
```

## QoR reporting

The summary infrastructure records only values it can parse from actual reports:

```text
Stage
WNS
TNS
Setup Violations
Worst Hold Slack
Hold Violations
Area
Utilization
Cell Count
Buffer Count
Inverter Count
Power
Congestion
DRC
Runtime
Status
```

Missing evidence is reported as `N/A` rather than fabricated.

Generated summaries:

```text
reports/summary/qor_summary.csv
reports/summary/qor_summary.json
reports/summary/qor_summary.md
```

## ECO methodology

The ECO path is measurement-driven:

1. capture pre-ECO setup/hold metrics;
2. create a candidate routed ECO;
3. legalize and route changed logic;
4. update timing;
5. compare before/after QoR;
6. accept only a non-regressing candidate;
7. otherwise keep the previous active block.

The flow never assumes an ECO helped merely because an optimization command completed.

## Physical verification

ICC2 in-design route/PG checks can run without a foundry signoff deck.

Foundry DRC/LVS status remains `UNKNOWN` unless qualified runsets are configured and actually executed. IR-drop/EM integration is preparation/handoff only unless a real supported analysis tool/model is available.

## Reproducibility

The project records:

- Git commit and dirty state
- project/top
- executable paths
- run ID
- stage runtime
- RTL/SDC/config hashes in run manifests where available
- logs and reports
- snapshots
- final SHA256 checksums

Use:

```bash
make snapshot
make release
```

`make release` performs final collection, release verification, and snapshot creation.

## Important outputs

```text
results/synthesis/
database/
checkpoints/
logs/
reports/
netlist/
spef/
extracted/
sdf/
gds/
final_delivery/
```

Expected final deliverables include, when successfully generated by the actual tool/PDK environment:

```text
MIPS_16.gds
MIPS_16_postroute.v
MIPS_16_postroute.sdf
MIPS_16_postroute.spef
MIPS_16_final.sdc
FINAL_SUMMARY.md
MANIFEST.txt
checksums.txt
```

## Cleaning and restart safety

```bash
make clean
```

Removes temporary work only.

```bash
make clean-results
```

Removes reports/logs/final assembled output while preserving implementation databases needed for resume semantics.

```bash
make distclean
```

Deliberately removes generated implementation databases, checkpoints, and artifacts. Source RTL, constraints, configuration, and technology inputs are protected by path checks.

## Documentation

- `docs/QUALITY_GATES.md` — execution vs engineering evidence vs foundry signoff
- `docs/QOR_REGRESSION.md` — baseline QoR gating
- `docs/COMMANDS.md` — tool command guide
- `docs/ASIC_FILE_FORMATS.md` — SDC/SDF/SPEF/SPF/NDM/GDS and other formats
- `docs/ASIC_FLOW_CHECKLIST.md` — RTL-to-GDSII checklist
- `docs/DEBUGGING.md` — timing/congestion/clock/DRC debugging
- `docs/FLOW_DIAGRAM.txt` — complete stage flow

## Important limitation

GitHub CI validates repository logic that does not require commercial EDA licenses or proprietary PDK data. It does **not** run Design Compiler, Formality, ICC2, PrimeTime, StarRC, or foundry DRC/LVS in GitHub-hosted CI. Real QoR and signoff status must come from an appropriately licensed implementation environment using the intended technology data.
