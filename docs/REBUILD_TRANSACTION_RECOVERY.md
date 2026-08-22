# Rebuild Transaction Recovery

The incremental rebuild engine archives stale stage evidence instead of deleting it. Invalidation is now journaled as a transaction so an interrupted or failed archive operation cannot silently leave the flow in a half-invalidated state.

## States

Each applied transaction writes `checkpoints/rebuild_transactions/<id>/transaction.json` and moves through explicit states:

```text
PREPARED -> APPLYING -> APPLIED
                 \
                  -> ROLLING_BACK -> ROLLED_BACK
                                   -> ROLLBACK_FAILED
```

A manual restore of an `APPLIED` transaction uses:

```text
APPLIED -> RESTORING -> RESTORED
                     -> RESTORE_FAILED
```

The JSON journal is rewritten atomically after every completed move.

## Safety behavior

Before moving any data, the transaction engine validates every source and destination. A missing source, duplicate source/destination, destination collision, or path outside the project root fails before the first move.

Evidence files are content-hashed with SHA-256 before/after archival. Large ICC2 database directories use a structural identity based on relative paths, sizes, mtimes, file count and total bytes so preservation can be checked without reading every database byte twice.

If an action fails after earlier actions succeeded, completed moves are restored in reverse order automatically. The journal records whether rollback itself succeeded.

## Applying a rebuild invalidation

First generate/review the plan normally. Then dry-run invalidation:

```bash
python3 python/apply_rebuild_plan.py
```

Apply after review:

```bash
python3 python/apply_rebuild_plan.py --apply
```

If the plan requires ICC2 initialization while `database/` is non-empty, preservation must be explicit:

```bash
python3 python/apply_rebuild_plan.py --apply --archive-database
```

The command prints `TRANSACTION_MANIFEST=<path>` for the journal that owns the archive operation.

## Restoring

A completed invalidation can be restored only while its original paths are still unoccupied:

```bash
python3 python/apply_rebuild_plan.py --restore checkpoints/rebuild_transactions/<id>/transaction.json
```

Restore refuses to overwrite newly generated stage evidence or a rebuilt ICC2 database. This makes rollback an explicit recovery action rather than an implicit destructive replacement.

`RESTORE_FAILED` and `ROLLBACK_FAILED` are intentionally terminal error states requiring engineer inspection; the flow never reports them as a successful rebuild.
