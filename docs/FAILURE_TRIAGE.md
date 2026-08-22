# Automatic EDA Failure Triage

Failed ASIC stages can generate a conservative investigation report automatically. The triage engine reads the stage log only after the underlying tool returns a nonzero exit code.

It does **not** modify the design, retry commands, change constraints, or claim that a matched text signature proves root cause.

## Automatic behavior

`scripts/common/run_stage.sh` invokes the triage engine after a failed stage and writes:

```text
reports/triage/<stage>.latest.json
reports/triage/<stage>.latest.md
```

The stage runtime metadata also records:

```text
triage_status
triage_primary
triage_category
triage_json
triage_markdown
```

The original EDA tool exit code is always preserved. A successful or failed triage classification cannot convert a failing stage into PASS.

## Current investigation categories

The signature database is stored in:

```text
config/failure_signatures.json
```

It includes conservative patterns for:

- license checkout/server failures;
- missing/unresolved tool executables;
- unsupported Tcl commands or release-specific options;
- missing required files;
- RTL parse/elaboration/reference failures;
- logical/physical library link failures;
- SDC/clock/unconstrained-path problems;
- parasitic/SPEF annotation failures;
- placement/routing/DRC symptoms;
- Formality non-equivalence symptoms;
- host memory/disk/resource exhaustion.

Several categories may match one log. Findings are ordered by configured priority and evidence count. This ordering is an investigation aid, not a probabilistic root-cause score.

## Manual triage

Any existing log can be analyzed without a Synopsys license:

```bash
./triage.sh logs/80_route_20260822_120000.log --stage route --tool icc2_shell --exit-code 1
```

This parses the log and writes the same JSON/Markdown evidence under `reports/triage/`.

## Interpretation rule

Every generated result contains:

```text
confidence = heuristic
root_cause_proven = false
```

A report may say, for example, that a log matches `required_input_missing` and `parasitic_annotation_failure`. The engineer should then inspect the earliest relevant tool error and stage reports. The flow must not automatically create a missing timing exception, rename a library cell, suppress a DRC, or modify a PDK path solely because a signature matched.

## Adding a signature

Add a new object to `config/failure_signatures.json` with:

```text
id
category
priority
patterns
guidance
```

Patterns are case-insensitive regular expressions. Keep them specific enough to avoid classifying ordinary informational text as a failure. Static CI compiles every pattern and unit tests verify that unrecognized failures remain `UNCLASSIFIED` rather than being forced into a known category.

## Recommended debugging order

1. Inspect the first fatal/error cluster in the original tool log.
2. Read the generated triage evidence and its matched line numbers.
3. Inspect stage-specific reports/checkpoints.
4. Check environment/fingerprint/provenance changes when the failure appears after a previously successful run.
5. Use the rebuild planner if a required upstream artifact is stale or missing.
6. Make only a justified design/configuration/tool correction, then rerun the affected dependency cone.

Triage is intentionally separated from signoff status: a classified failure is still a failure, and an unclassified failure still requires investigation.
