# Synopsys Command Guide

## Design Compiler
- `analyze`: parses RTL into intermediate design units.
- `elaborate`: selects/parameterizes the top design.
- `link`: resolves design/library references.
- `uniquify`: gives independently optimized instances unique design copies when needed.
- `compile_ultra`: technology maps and optimizes timing/area/power objectives.
- `check_design`: structural consistency check.
- `check_timing`: timing-constraint sanity check.
- `report_timing`: detailed timing paths.
- `report_area`: mapped cell-area accounting.
- `report_power`: library/activity-based power estimate.
- `report_qor`: high-level timing/area QoR summary.
- `write`: writes Verilog/DDC.
- `write_sdc`: exports constraints.
- `write_sdf`: exports timing annotation when supported.
- `set_svf`: records synthesis guidance for Formality.

## Formality
- `read_db`: reads technology/library models.
- `read_verilog -container r|i`: reads Verilog reference or implementation design.
- `read_sverilog -container r|i`: reads SystemVerilog into the selected Formality container.
- `set_top`: elaborates/sets container top.
- `match`: pairs compare points.
- `verify`: proves equivalence; documented flows use its boolean return status.
- `report_failing_points`, `report_aborted_points`, `report_unmatched_points`: failure diagnosis.
- `set_svf`: loads DC guidance.

## PrimeTime
- `read_verilog`: loads gate netlist.
- `link_design`: resolves library cells.
- `read_parasitics`: annotates SPEF parasitic R/C.
- `update_timing`: updates timing graph/arrival/required times.
- `check_timing`: audits timing setup and unconstrained structures.
- `report_timing -delay_type max`: setup/late analysis.
- `report_timing -delay_type min`: hold/early analysis.
- `report_global_timing`: WNS/TNS-style summary when available.
- `set_propagated_clock`: uses implemented clock-network latency.
- `report_power` / `update_power`: power analysis in licensed PX flows.

## IC Compiler II
- `create_lib`: creates writable NDM design library attached to reference NDMs/technology.
- `open_lib`, `open_block`, `current_block`: navigate NDM library/block databases.
- `read_verilog`: imports mapped netlist into physical database.
- `link_block`: resolves leaf cells against NDM references.
- `initialize_floorplan`: creates die/core geometry from utilization/shape/boundary criteria.
- `set_cell_location`: places an explicitly configured macro at reviewed coordinates/orientation.
- `create_keepout_margin`: applies a macro halo/keepout.
- `create_placement_blockage`, `create_routing_blockage`: create explicit physical blockages.
- `create_net -power|-ground`: creates PG logical nets.
- `connect_pg_net`: connects PG pins/ports to supply nets.
- `create_pg_ring_pattern`, `create_pg_mesh_pattern`: define reusable PG ring/mesh geometry patterns.
- `create_pg_std_cell_conn_pattern`: defines standard-cell power rails on a PDK-valid layer.
- `create_pg_macro_conn_pattern`: defines macro power-pin connection behavior such as scattered-pin extension.
- `set_pg_strategy`: binds a PG pattern to core/region/net intent.
- `compile_pg`: instantiates the selected PG strategy.
- `place_opt`: timing/congestion-aware placement/optimization.
- `set_clock_tree_options`: applies optional target skew/latency policy.
- `set_clock_routing_rules`: constrains clock routing layers/NDR policy when configured.
- `clock_opt`: CTS plus clock/data optimization.
- `route_auto`: automatic routing.
- `route_opt`: post-route timing/route optimization.
- `check_routes`: route completeness/route-rule evidence; not equivalent to foundry signoff DRC.
- `check_pg_connectivity`, `check_pg_drc`: PG integrity checks.
- `write_parasitics`: writes SPEF/SBPF on releases supporting this interface.
- `write_verilog`, `write_sdc`, `write_sdf`: implementation handoff files.
- `write_gds -layer_map`: streams GDSII with an explicit technology mapping file.
- `save_block -as`: stores a named NDM block checkpoint.

Commands may gain/lose options between releases; repository guards optional reporting commands and marks technology/release-sensitive sections rather than fabricating syntax.

## StarRC
- `StarXtract -clean <command_file>`: starts a clean batch extraction from a PDK-qualified StarRC command file.

## GUI capture
- `gui_zoom -fit`: fits the design in the active layout window.
- `gui_write_window_image`: saves a PNG/JPG/etc. image of a GUI/layout window.

## Constraint audit
- `report_exceptions`: audits timing exceptions.
- `report_case_analysis -all`: reports explicit and propagated case-analysis constants where supported.
- `report_disable_timing`: reports disabled timing arcs and their causes.
