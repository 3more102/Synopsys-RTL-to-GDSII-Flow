# Stage Lock Ownership and Recovery

Long-running ASIC stages must not allow two writers to modify the same generated database concurrently. `scripts/common/run_stage.sh` therefore uses an atomic directory lock under:

```text
work/locks/<stage>.lock/
```

Each acquired lock contains `owner.json` with the runner PID/PPID, host, Linux boot identity when available, process-start identity, stage, tool, Tcl script and `FLOW_RUN_ID`.

## Inspect locks

```bash
./locks.sh list
```

Inspect one stage:

```bash
./locks.sh check --stage route
```

Possible states:

- `FREE`: no lock directory exists.
- `ACTIVE`: the recorded local runner process is still alive and matches its process-start identity.
- `STALE`: the lock is from the same host name but a different boot identity. Processes from that boot cannot still be alive.
- `FOREIGN_HOST`: the lock was created on another host. Local automatic recovery is forbidden.
- `UNKNOWN`: ownership cannot be proven safely. Examples include a missing/corrupt owner file or a runner PID that died during the same boot, because an EDA child might have survived its parent.

## Safe recovery after reboot

A proven `STALE` lock can be archived:

```bash
./locks.sh recover --stage route
```

The lock directory is moved—not deleted—to:

```text
work/stale_locks/<timestamp>_route.lock/
```

with `recovery.json` describing the prior ownership evidence.

`run_stage.sh` can do this automatically only for proven `STALE` locks when explicitly enabled:

```bash
FLOW_RECOVER_STALE_LOCKS=1 make route
```

It never auto-recovers `UNKNOWN`, `ACTIVE` or `FOREIGN_HOST` locks.

## Same-boot orphan

A dead runner PID during the same boot is intentionally classified `UNKNOWN`, not `STALE`. Killing or losing the wrapper shell does not prove that ICC2/PrimeTime/DC/Formality children stopped.

After independently confirming that no relevant EDA process remains, an engineer may explicitly archive an `UNKNOWN` lock:

```bash
./locks.sh recover --stage route --force-unknown
```

This still refuses `ACTIVE` and `FOREIGN_HOST` locks.

## Signal handling

The runner installs signal handlers that exit nonzero on INT/TERM/HUP and lets its EXIT trap remove only the generated `owner.json` plus an empty lock directory. It does not use recursive deletion for lock cleanup.

## Design intent

The lock mechanism protects metadata/database writers. It is deliberately conservative: inability to prove a lock safe to recover results in refusal rather than an optimistic unlock. The recovery archive remains available for postmortem analysis.
