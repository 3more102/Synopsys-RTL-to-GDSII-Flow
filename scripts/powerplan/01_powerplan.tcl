# =============================================================================
# Stage       : Power planning
# Tool        : Synopsys IC Compiler II
# Description : Connects logical PG and builds configured ring, mesh, std-cell rails and macro connections.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "POWER PLANNING"
open_stage_block floorplan
foreach v {PG_RING_H_LAYER PG_RING_V_LAYER PG_MESH_H_LAYER PG_MESH_V_LAYER PG_STD_CELL_RAIL_LAYER} {
    require_nonempty [set $v] $v
}
if {[sizeof_collection [get_nets -quiet $VDD_NET]] == 0} { create_net -power $VDD_NET }
if {[sizeof_collection [get_nets -quiet $VSS_NET]] == 0} { create_net -ground $VSS_NET }
set _vdd_pins [get_pins -physical_context -quiet "*${VDD_PORT_PATTERN}"]
set _vss_pins [get_pins -physical_context -quiet "*${VSS_PORT_PATTERN}"]
if {[sizeof_collection $_vdd_pins] == 0 || [sizeof_collection $_vss_pins] == 0} {
    fatal_error "PG pin patterns did not match both VDD and VSS pins. Review VDD_PORT_PATTERN/VSS_PORT_PATTERN against the NDM library."
}
connect_pg_net -net $VDD_NET $_vdd_pins
connect_pg_net -net $VSS_NET $_vss_pins
if {$ENABLE_PG_GEOMETRY} {
    create_pg_ring_pattern CORE_RING \
        -horizontal_layer $PG_RING_H_LAYER -horizontal_width $PG_RING_WIDTH -horizontal_spacing $PG_RING_SPACING \
        -vertical_layer $PG_RING_V_LAYER -vertical_width $PG_RING_WIDTH -vertical_spacing $PG_RING_SPACING
    set_pg_strategy CORE_RING_STRAT -core \
        -pattern [list [list name: CORE_RING] [list nets: [list $VDD_NET $VSS_NET]] [list offset: [list $PG_RING_OFFSET $PG_RING_OFFSET]]]
    compile_pg -strategies CORE_RING_STRAT
    create_pg_mesh_pattern CORE_MESH -layers [list \
        [list [list horizontal_layer: $PG_MESH_H_LAYER] [list width: $PG_MESH_H_WIDTH] [list spacing: interleaving] [list pitch: $PG_MESH_H_PITCH]] \
        [list [list vertical_layer: $PG_MESH_V_LAYER] [list width: $PG_MESH_V_WIDTH] [list spacing: interleaving] [list pitch: $PG_MESH_V_PITCH]]]
    set_pg_strategy CORE_MESH_STRAT -core \
        -pattern [list [list name: CORE_MESH] [list nets: [list $VDD_NET $VSS_NET]]]
    compile_pg -strategies CORE_MESH_STRAT
    if {$PG_STD_CELL_RAIL_WIDTH eq ""} {
        create_pg_std_cell_conn_pattern STD_CELL_RAIL -layers [list $PG_STD_CELL_RAIL_LAYER]
    } else {
        create_pg_std_cell_conn_pattern STD_CELL_RAIL -layers [list $PG_STD_CELL_RAIL_LAYER] \
            -rail_width [list $PG_STD_CELL_RAIL_WIDTH $PG_STD_CELL_RAIL_WIDTH]
    }
    set_pg_strategy STD_CELL_RAIL_STRAT -core \
        -pattern [list [list name: STD_CELL_RAIL] [list nets: [list $VDD_NET $VSS_NET]]]
    compile_pg -strategies STD_CELL_RAIL_STRAT
    set _macros [get_cells -hierarchical -quiet -filter "is_hard_macro==true"]
    if {[sizeof_collection $_macros] > 0} {
        create_pg_macro_conn_pattern MACRO_PG_CONN -pin_conn_type scattered_pin
        set_pg_strategy MACRO_PG_STRAT -macros $_macros \
            -pattern [list [list name: MACRO_PG_CONN] [list nets: [list $VDD_NET $VSS_NET]]]
        compile_pg -strategies MACRO_PG_STRAT
    }
}
report_if_supported check_pg_connectivity [file join $REPORT_DIR powerplan pg_connectivity.rpt]
report_if_supported check_pg_drc [file join $REPORT_DIR powerplan pg_drc.rpt]
icc2_basic_reports powerplan
save_stage_block powerplan
write_status powerplan WARNING "PG construction completed. Connectivity/PG-DRC reports must be reviewed; no clean signoff result is inferred automatically."
stage_complete "POWER PLANNING"
exit 0
