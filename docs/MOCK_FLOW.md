# Deterministic Mock Flow

GitHub-hosted CI cannot run licensed Synopsys tools or proprietary PDK decks. The repository therefore provides a deterministic mock layer for testing orchestration, parsing, failure handling and safety behavior without pretending to perform ASIC signoff.

## Safety boundary

Mock runs are written under:

```text
work/mock_runs/<scenario>/
```

by default. They never populate the real repository `reports/`, `database/`, `gds/`, `spef/` or `final_delivery/` trees.

Every mock report contains:

```text
MOCK DATA - NOT SIGNOFF
```

Every mock status uses `MOCK_PASS`, `MOCK_FAIL` or `MOCK_GENERATED` rather than the real flow's PASS/FAIL/GENERATED values. `MOCK_RUN.json` always contains:

```json
{
  "mock": true,
  "signoff_qualified": false
}
```

The `.gds` file in a mock run is intentionally plain text saying that it is not GDSII stream data.

## Run scenarios

Clean parser/orchestration smoke test:

```bash
./mock_flow.sh --scenario clean
```

Setup-timing failure:

```bash
./mock_flow.sh --scenario timing_fail
```

Routing DRC failure:

```bash
./mock_flow.sh --scenario drc_fail
```

License checkout failure log:

```bash
./mock_flow.sh --scenario license_fail
```

Missing extracted SPEF/artifact failure:

```bash
./mock_flow.sh --scenario missing_artifact
```

The wrapper generates the scenario and immediately validates it with the repository's real QoR parsing functions.

## What is tested

The validator uses `qor_parsers.py` and `report_utils.py` to prove that representative report text is still understood by the same parsers used by the real flow. Tests cover:

- synthesis WNS/TNS/violation parsing;
- signoff setup and hold parsing;
- area/cell-count parsing;
- power parsing;
- placement congestion parsing;
- route DRC parsing;
- explicit mock-only status vocabulary;
- deterministic generated payloads;
- license-failure classification through the existing triage signatures;
- missing-artifact behavior;
- refusal to `--force` replace an arbitrary non-mock directory.

## Replacing a mock run

A mock output directory is not overwritten by default. `--force` is accepted only when the destination already contains a valid `MOCK_RUN.json` marker with `mock=true`:

```bash
./mock_flow.sh --scenario clean --force
```

This avoids turning test cleanup into a generic destructive directory operation.

## Interpretation

A mock validation result of `PASS` means **the test scenario behaved as designed**. It never means timing, DRC, LVS, power, extraction or streamout passed for a real design. No mock artifact may be promoted to a real release baseline or final delivery.
