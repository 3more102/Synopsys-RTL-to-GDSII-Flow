# Rebuild Planning and QoR Dashboard

This repository includes license-free utilities that operate on existing flow evidence and repository metadata. Planning itself does not launch Design Compiler, ICC2, PrimeTime, Formality, StarRC, or ICV.

## Rebuild planner

Run:

```bash
./plan_flow.sh
```

The planner reads:

- `config/stage_graph.json` for the canonical dependency DAG and Make-target mapping;
- `config/fingerprint_policy.json` for stage input identities;
- `checkpoints/fingerprints/*.json` for captured fingerprints;
- stage checkpoint/status evidence.

It writes:

```text
reports/summary/rebuild_plan.json
reports/summary/rebuild_plan.md
```

A stage is classified as:

- `NOT_RUN`: no checkpoint/status evidence exists;
- `FRESH`: saved fingerprint matches current inputs;
- `STALE`: RTL/config/PDK/tool identity changed;
- `UNVERIFIABLE`: checkpoint exists but no saved fingerprint exists;
- `NO_POLICY`: evidence exists but no fingerprint policy is defined;
- `ERROR`: the fingerprint checker itself could not complete.

When a stale or unverifiable upstream stage is found, downstream stages in the DAG are marked for rebuild. The report contains both the canonical ASIC stage and its actual Make target.

To include stages that have never run and obtain a complete build plan:

```bash
./plan_flow.sh --include-not-run
```

To limit analysis to the dependency cone required to produce a specific stage:

```bash
./plan_flow.sh --stage route --include-not-run
```

To use stale evidence as a CI/pre-run gate:

```bash
./plan_flow.sh --fail-on-stale
```

The advisory command does not fail merely because a stage has never run unless `--include-not-run` is requested.

## Flow-model consistency audit

The static CI now checks that the three independent control layers agree:

```text
config/stage_graph.json
config/fingerprint_policy.json
Makefile
```

`python/validate_flow_model.py` verifies:

- the DAG is acyclic;
- every dependency references a real stage;
- every graph stage maps to a real Make target;
- every graph stage maps to a defined fingerprint stage;
- Make-target aliases in the fingerprint policy resolve to the expected canonical stage;
- evidence paths remain repository-relative and inside checkpoint/status areas.

A mismatch fails static validation before any licensed tool is started.

## Safe executable rebuild plan

The main flow runner can convert the plan into an executable rebuild without using `make -B` and without deleting source or implementation databases:

```bash
./run_flow.sh --plan
```

This validates the flow model, includes required never-run stages, and reports the exact ordered Make targets.

After reviewing the plan:

```bash
./run_flow.sh --execute-plan
```

Execution performs a transaction-like invalidation step first. Existing stale evidence files are **moved**, not deleted, into:

```text
checkpoints/stale_archive/<timestamp>/
```

with an `invalidation_manifest.json` describing every moved file and the source plan. Removing the stale stamps makes normal Make dependency logic rerun exactly the selected stages.

A non-destructive preview is available:

```bash
./run_flow.sh --execute-plan --dry-run
```

The preview prints the ordered Make commands and moves nothing.

### ICC2 database safety

If the rebuild plan includes `icc2_init` and `database/` is non-empty, execution stops. Reinitializing an NDM design library over an existing database can fail or create ambiguous state.

To explicitly approve archival of the existing generated database:

```bash
./run_flow.sh --execute-plan --archive-database
```

The database directory is moved to:

```text
runs/stale_database_archive/<timestamp>/database/
```

and a fresh `database/` directory is created. The old implementation database is preserved for recovery; it is never removed by the planner.

A stage-limited execution is also supported:

```bash
./run_flow.sh --execute-plan route
```

Only the dependency cone needed to produce `route` is considered.

The DAG complements Make dependencies. It exists to catch cases timestamps cannot represent reliably, such as a library database changing in place or a PDK/tool identity changing while checkpoint timestamps remain newer than source files.

## QoR HTML dashboard

Run:

```bash
./dashboard.sh
```

The generator reads existing machine-readable evidence when available:

```text
reports/summary/qor_summary.json
reports/summary/release_verification.json
reports/summary/qor_regression.json
reports/summary/rebuild_plan.json
```

and creates:

```text
reports/summary/dashboard.html
```

The dashboard is self-contained HTML with no external JavaScript, CSS, Python package, or network dependency. It displays stage-level WNS, TNS, setup/hold violations, area, utilization, power, congestion, DRC count, runtime, and status when those values were actually parsed.

Missing metrics remain `N/A`. The dashboard never turns missing data into a passing signoff claim.

Recommended sequence after a real implementation run:

```bash
python3 python/generate_summary.py
./plan_flow.sh
./dashboard.sh
```

For a release-quality review, also run:

```bash
python3 python/verify_artifacts.py
QOR_BASELINE=/path/to/known-good/qor_summary.json make qor-gate
./dashboard.sh
```

## Final-delivery integration

`scripts/final/collect_deliverables.sh` refreshes the rebuild plan and dashboard before copying summary reports into the release package. Therefore a normal `make final`/`make release` archives:

```text
final_delivery/qor/rebuild_plan.json
final_delivery/qor/rebuild_plan.md
final_delivery/qor/dashboard.html
```

when those files can be generated from the available evidence. They are then included in the final SHA256 checksum inventory together with the other release artifacts.

The rebuild plan is engineering evidence rather than signoff evidence. Release acceptance remains controlled by artifact verification, QoR/timing gates, and qualified physical verification—not by silently deleting or regenerating implementation databases.

The final HTML page is intended for engineering review and run archiving. It does not replace PrimeTime reports, foundry-qualified DRC/LVS, IR/EM signoff, or silicon validation.
