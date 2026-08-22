# Rebuild Planning and QoR Dashboard

This repository includes two license-free utilities that operate only on existing flow evidence. They do not launch Design Compiler, ICC2, PrimeTime, Formality, StarRC, or ICV.

## Rebuild planner

Run:

```bash
./plan_flow.sh
```

The planner reads:

- `config/stage_graph.json` for the logical dependency DAG;
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

When a stale or unverifiable upstream stage is found, downstream stages in the DAG are marked for rebuild. The report includes `REBUILD_FROM=<stage>` for the earliest affected stage.

To limit the analysis to the dependency cone required to produce a specific stage:

```bash
./plan_flow.sh --stage route
```

To use the planner as a CI/pre-run gate:

```bash
./plan_flow.sh --fail-on-stale
```

That command exits nonzero only when the planner proves that existing checkpoint evidence should be rebuilt. It does not fail simply because a stage has never been run.

The DAG is advisory planning metadata and does not replace Make dependencies. It exists to catch cases that timestamps cannot represent reliably, such as a library file changing in place or a PDK/tool identity changing while checkpoint timestamps remain newer than source files.

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

The final HTML page is intended for engineering review and run archiving. It does not replace PrimeTime reports, foundry-qualified DRC/LVS, IR/EM signoff, or silicon validation.
