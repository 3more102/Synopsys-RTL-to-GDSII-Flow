# ASIC File Formats

| Format | Purpose |
|---|---|
| `.v` | Verilog RTL or gate-level netlist. |
| `.sv` | SystemVerilog RTL/netlist. |
| `.sdc` | Synopsys Design Constraints: clocks, I/O delays, uncertainty, exceptions, design rules. It describes **timing intent**, not delays extracted from implementation. |
| `.lib` | Human-readable Liberty cell timing/power/function models. |
| `.db` | Synopsys compiled Liberty/library database. |
| `.lef` | Abstract physical cell/routing technology descriptions commonly used in LEF/DEF flows. |
| `.def` | Placed/routed design exchange description. |
| `.ndm` | Synopsys New Data Model physical/logical library/database format used by ICC2/Fusion flows. |
| `.ddc` | Design Compiler binary design database. |
| `.upf` | IEEE 1801 power intent: domains, supplies, isolation, retention, level shifting. |
| `.spef` | Standard Parasitic Exchange Format containing extracted net resistance/capacitance/coupling. |
| `.spf/.dspf` | Standard/Detailed Parasitic Format; transistor/netlist-style parasitic representation, often more detailed than SPEF workflows. |
| `.sdf` | Standard Delay Format used to back-annotate cell/interconnect timing into gate-level simulation. |
| `.saif` | Switching Activity Interchange Format for power activity. |
| `.vcd` | Value Change Dump simulation waveform/activity file. |
| `.gds` | GDSII mask-layout stream format. |
| `.oas` | OASIS layout stream format, generally more compact than GDSII. |

## SDC vs SDF vs SPEF/SPF

- **SDC** says what timing the design must satisfy: clock periods, external delays, uncertainty, false/multicycle paths and design-rule limits.
- **SDF** says modeled delays to annotate into a gate-level timing simulation.
- **SPEF/SPF/DSPF** says physical parasitic resistance/capacitance extracted from interconnect, used by timing/power/signoff engines to calculate delay/noise accurately.

They are complementary and are not interchangeable.
