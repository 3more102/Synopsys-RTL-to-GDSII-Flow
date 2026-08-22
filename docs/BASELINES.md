# QoR and Provenance Baselines

The flow supports controlled promotion of a known run into a local comparison baseline. This avoids manually copying `qor_summary.json` or provenance files and accidentally comparing against an unverified or modified reference.

Local baselines are stored under:

```text
baselines/local/<name>/
```

`baselines/local/` is ignored by Git by default because provenance may contain workstation, PDK, library, and tool paths.

## Promote the current verified run

```bash
./baseline.sh promote golden_2026_08_22
```

This command requires, by default:

- `reports/summary/qor_summary.json`;
- `reports/provenance/run_provenance.json`;
- `reports/summary/release_verification.json` with `status=PASS`.

It copies the available QoR/provenance/release evidence into the named baseline and writes `BASELINE.json` containing SHA256 hashes, provenance identity, Git identity, release status, and whether the baseline is provisional.

A failed or `UNKNOWN` release is not silently promoted.

## Promote an archived run

```bash
./baseline.sh promote golden_postroute --source runs/2026-08-22_asic_run
```

The archived run must contain the same report structure as a normal run snapshot.

## Provisional baseline

For development-only comparisons, an unverified run may be promoted explicitly:

```bash
./baseline.sh promote experimental --allow-unverified
```

The resulting `BASELINE.json` records `provisional: true`. This flag does not turn the run into signoff-quality evidence.

## Inspect and verify

```bash
./baseline.sh list
```

Lists local baselines with baseline-integrity state, release status, and provenance digest.

```bash
./baseline.sh verify golden_2026_08_22
```

Recomputes the copied evidence hashes and fails if the baseline was modified or corrupted after promotion.

```bash
./baseline.sh show golden_2026_08_22
```

Prints the baseline metadata.

## Use the baseline for QoR regression

```bash
QOR_BASELINE="$(./baseline.sh path golden_2026_08_22)" make qor-gate
```

The baseline manager returns the exact `qor_summary.json` path. `make qor-gate` then applies `config/qor_policy.json` to compare the current run against that known reference.

## Use the same baseline for provenance comparison

```bash
PROVENANCE_BASELINE="baselines/local/golden_2026_08_22/run_provenance.json" make compare-provenance
```

This distinguishes design/methodology/technology identity changes from execution-environment changes.

For a stricter comparison of execution identity as well:

```bash
PROVENANCE_BASELINE="baselines/local/golden_2026_08_22/run_provenance.json" STRICT_EXECUTION=1 make compare-provenance
```

## Replace a baseline safely

An existing baseline name is immutable by default. To deliberately replace one:

```bash
./baseline.sh promote golden_2026_08_22 --replace
```

The previous baseline is moved into:

```text
baselines/local/.archive/<timestamp>_golden_2026_08_22/
```

before the new baseline is created. The previous reference is not deleted.

## Publishing baselines

Do not commit `baselines/local/` without reviewing its provenance content. If a baseline must be shared publicly, create a separately scrubbed/reference package that contains only information approved for publication. Do not remove or rewrite PDK/tool provenance merely to make a comparison pass; instead document the intentionally omitted fields and treat the published baseline as a different evidence class.
