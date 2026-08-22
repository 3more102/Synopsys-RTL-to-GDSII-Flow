# Required Stage Output Gates

A proprietary tool process returning exit code `0` is necessary but not sufficient evidence that an ASIC stage completed usefully. A synthesis shell can exit cleanly while a mapped netlist path is wrong, stream-out can be redirected unexpectedly, or a generated file can be empty.

The flow therefore validates required generated artifacts **before** capturing a reusable stage fingerprint.

## Contract source

Required/optional generated files are declared centrally in:

```text
config/artifact_provenance.json
```

The same contract drives artifact lineage and stage output validation, avoiding a second independent list of expected filenames.

Current hard-output examples include:

- synthesis mapped Verilog and SDC;
- post-route netlist and final SDC;
- extracted SPEF;
- final GDSII stream file.

Optional artifacts such as synthesis/post-route SDF or OASIS do not fail a stage unless promoted to a required contract entry.

## Validation rules

For every configured `required` pattern, `python/validate_stage_outputs.py` requires at least one match that:

1. resolves inside the project root;
2. is a regular file;
3. is non-empty.

A symlink that resolves outside the repository, an empty file, a directory, or a missing pattern does not satisfy the contract.

The validator writes machine-readable evidence to:

```text
reports/status/<stage>_outputs.json
```

and returns nonzero when required outputs are unusable.

## Runner ordering

`scripts/common/run_stage.sh` executes validation in this order:

```text
EDA process
  ↓
required output contract
  ↓
fingerprint capture
  ↓
runtime metadata / lineage
```

This ordering prevents an apparently successful process from creating a reusable `FRESH` checkpoint fingerprint when its required artifacts are missing.

If the EDA process returns `0` but the output contract fails, the runner converts the stage to flow exit code `76`. Failure triage classifies the event under the heuristic `artifact_output` category; this does not claim a root cause, only the proven symptom that required output evidence is missing or unusable.

## Manual validation

For diagnosis:

```bash
python3 python/validate_stage_outputs.py --stage synthesis
```

A stage with no configured required artifact contract returns `SKIP`, not `PASS`.

## Diagnostic escape hatch

Output gating is enabled by default. It can be disabled explicitly for tool-debug sessions:

```bash
STAGE_OUTPUT_GATE=0 make synth
```

The runner logs a warning when this is used. Disabling the gate is not appropriate for a release-quality run because it permits process success without proving required files.

## Relation to signoff

An output gate proves only file existence/usability according to the declared contract. It does **not** prove:

- timing closure;
- parasitic quality;
- DRC/LVS cleanliness;
- power accuracy;
- foundry qualification;
- silicon correctness.

Those remain independent report/status/release gates.
