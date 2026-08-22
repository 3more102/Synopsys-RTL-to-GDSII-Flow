# Freshness, SDC Safety, and Tool Compatibility

This layer prevents three common classes of expensive ASIC-flow mistakes: reusing checkpoints after invisible environment/PDK changes, accepting over-broad timing exceptions, and discovering Synopsys release incompatibilities only after a long stage starts.

## Stage input fingerprints

Every successful stage launched through `scripts/common/run_stage.sh` attempts to capture `checkpoints/fingerprints/<stage>.json`. Repository files are SHA-256 content hashed. Large external technology/library inputs use configured path, size, and modification time by default; set `FINGERPRINT_EXTERNAL_PATH_MODE=sha256` when full external-file hashing is practical.

```bash
make fingerprint STAGE=synth
make freshness STAGE=synth
make freshness STAGE=synth DETAILS=1
```

`run_flow.sh` is freshness-aware. Before reusing an existing Make checkpoint that GNU Make considers current, it checks the saved fingerprint. If environment/PDK/tool identity changed, the runner stops rather than silently reusing the checkpoint. Set `FLOW_FRESHNESS_CHECK=0` only for a deliberate bypass.

This closes a gap in Make timestamps: shell values such as `TARGET_LIBRARY`, `STD_CELL_NDM`, `TLU_PLUS_MAX`, `CLOCK_PERIOD`, `CORE_UTILIZATION`, or PG layer settings can change while repository files remain untouched.

## Static SDC safety audit

```bash
make sdc-audit
```

Reports are written to `reports/audit/sdc_audit.json` and `reports/audit/sdc_audit.md`. The audit flags global false paths, broad wildcard collections inside risky exceptions, false-pathing all registers, malformed asynchronous clock groups, disabled timing arcs, case analysis, suspicious multicycle setup/hold pairing, and absence of an active `create_clock`.

Policy lives in `config/sdc_audit_policy.json`. This is a heuristic review aid only; it does not replace tool-native `check_timing`, timing coverage, `report_exceptions`, `report_constraint`, or detailed STA review.

## Synopsys capability probe

```bash
make capabilities
REQUIRE_TOOL_CAPABILITIES=1 make capabilities
```

The probe starts each installed shell with a read-only Tcl script and uses `info commands`; commands under test are not executed and no design is read. Results are under `reports/capabilities/`. Missing tools are `UNKNOWN` by default. Installed tools that lack a configured required command are `FAIL`. `REQUIRE_TOOL_CAPABILITIES=1` also makes unavailable tools blocking.

The expected command set is reviewable in `config/tool_capabilities.json`.

## Combined flow doctor

```bash
make doctor
```

Runs license-free repository/config/unit-test/SDC checks, then the advisory capability probe.

Recommended pre-run sequence:

```bash
source setup.sh
make doctor
make env
./run_flow.sh --from synth --to floorplan
```

After a known-good run, preserve `reports/summary/qor_summary.json` as the baseline for the repository's QoR regression gate.
