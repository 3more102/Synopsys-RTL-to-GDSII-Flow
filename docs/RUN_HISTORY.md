# Run History and QoR Trend Index

The flow can build a historical engineering view from archived run snapshots without invoking any licensed EDA tool.

## Generate history

```bash
./history.sh
```

This scans `runs/*/` snapshots and writes:

```text
reports/history/run_history.json
reports/history/run_history.csv
reports/history/run_history.md
reports/history/run_history.html
```

To include the current working report set even before it is archived:

```bash
./history.sh --include-current
```

To limit indexing to the newest archived runs:

```bash
./history.sh --limit 20
```

## Metrics

For each run, the indexer uses the most signoff-relevant evidence available:

- WNS/TNS: Signoff, then Post-Route, then Route fallback;
- worst hold slack: Signoff, then routed/post-CTS fallback;
- area/utilization/cell count: Post-Route first, then earlier physical stages;
- power: Signoff power first when present;
- runtime: sum of parsed stage runtimes in `qor_summary.json`;
- provenance digest and Git identity from the archived run metadata;
- release-verification and QoR-regression status when those reports exist.

No metric is invented. Missing values remain `N/A`.

## Automatic snapshot integration

`scripts/common/create_run_snapshot.sh` now runs the history indexer after a new snapshot is complete. It then refreshes the copy under that snapshot so the archived run contains a history table that includes itself.

This allows a snapshot to remain self-describing even if the live `reports/` directory is later cleaned.

## Final delivery

`scripts/final/collect_deliverables.sh` runs the history indexer with `--include-current` before packaging and copies the outputs into:

```text
final_delivery/history/
```

These files are therefore included in the final SHA256 checksum inventory.

## Interpretation

Historical trends are for engineering comparison, not signoff substitution. A better WNS trend does not prove closure unless the corresponding PrimeTime setup/hold evidence and configured release gates pass. Likewise, the history dashboard does not replace foundry DRC/LVS, IR/EM analysis, or silicon characterization.
