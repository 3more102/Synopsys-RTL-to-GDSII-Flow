# MMMC Signoff Coverage

The repository keeps multi-mode/multi-corner intent in `config/corners.tcl`, `config/modes.tcl`, and `config/scenarios.tcl`. The default project intentionally leaves the conceptual setup/hold scenarios disabled until real PVT libraries are configured.

Run the structural audit with:

```bash
make mmmc-audit
```

When no scenario is enabled, status is `UNKNOWN` rather than `FAIL`; this means the base single-corner flow is still valid but MMMC signoff is not active.

Once scenarios are enabled, the audit checks:

- every scenario references an existing mode and corner;
- every enabled scenario uses an enabled mode;
- enabled modes point to an existing SDC;
- enabled scenarios use corners with configured libraries;
- every enabled mode has both setup-purpose and hold-purpose scenario coverage;
- setup corners use the configured max-RC role and hold corners use min-RC role.

Reports:

```text
reports/mmmc/mmmc_coverage.json
reports/mmmc/mmmc_coverage.md
```

For signoff evidence completeness, use:

```bash
make mmmc-signoff-audit
```

This requires at least one enabled MMMC scenario and checks scenario-specific reports using the templates in `config/mmmc_coverage_policy.json`, for example:

```text
reports/signoff/scenarios/func_setup/setup.rpt
reports/signoff/scenarios/func_hold/hold.rpt
```

The evidence audit does not claim that a report is timing-clean merely because the file exists; it only proves that the expected scenario evidence was generated. Timing PASS/FAIL remains report/parser driven.
