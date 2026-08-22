# Debug Strategy

## Setup
Inspect `scripts/debug/debug_setup.tcl` output for logic depth, cell/net delay, clock path, transition/capacitance and slack. Candidate remedies include sizing, buffering, logic restructuring, placement improvement, routing improvement or architectural pipelining; select based on the actual delay breakdown.

## Hold
Inspect shortest paths and clock skew first. Delay insertion must use legal library cells and be rechecked for setup impact.

## Congestion
Check utilization and hotspots. Remedies include lower utilization, macro movement, halo/channel changes, partial blockages, padding or routing-layer policy. Do not apply all simultaneously without measuring QoR.

## Clock
Review sink count, skew, insertion delay, transition and clock-cell usage. Avoid treating clocks as ordinary high-fanout data nets.

## DRC/DRV
`max_transition`, `max_capacitance`, and `max_fanout` are timing/design-rule constraints; they are distinct from geometric foundry DRC.
