# QoR Regression Gate

The flow can compare a new `reports/summary/qor_summary.json` against a known-good baseline and fail when configured QoR rules regress.

```bash
QOR_BASELINE=/path/to/baseline/qor_summary.json make qor-gate
```

or directly:

```bash
python3 python/check_qor_regression.py \
  --baseline runs/golden/reports/summary/qor_summary.json \
  --current reports/summary/qor_summary.json \
  --policy config/qor_policy.json
```

The result is written to:

- `reports/summary/qor_regression.json`
- `reports/summary/qor_regression.md`

## Default policy

`config/qor_policy.json` is methodology policy, not PDK data. Review it for every project.

- Signoff WNS, TNS and worst hold slack must be present, remain non-negative, and must not regress versus the baseline.
- Post-route timing must not regress when both runs provide the metric.
- Post-route routing-violation count is required to be zero only when that metric is available; this is an in-design routing check, not foundry DRC signoff.
- Area/power/congestion/runtime allowances are explicit policy values and default to warnings rather than silently blocking tapeout.

A missing metric is never converted to zero. Rules marked `require_current` or `require_baseline` fail if evidence is absent; optional rules are reported as `SKIP`.

This gate complements `make verify`: `verify` checks release artifacts/status evidence, while `qor-gate` checks regression against a previous known-good run.
