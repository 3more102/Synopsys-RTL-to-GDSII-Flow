# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 01_floorplan.tcl
# Stage       : Floorplanning
# Tool        : Synopsys IC Compiler II
# Run         : icc2_shell -f scripts/floorplan/01_floorplan.tcl
# Description : Creates die/core geometry and applies only explicitly configured physical constraints.
# =============================================================================
source [file join [file dirname [info script]] icc2_common.tcl]
stage_banner "FLOORPLAN"
open_stage_block init
if {$FLOORPLAN_USE_EXPLICIT_DIE} {
    require_nonempty $DIE_BOUNDARY DIE_BOUNDARY
    initialize_floorplan -control_type die -boundary $DIE_BOUNDARY -core_offset $CORE_OFFSET
} else {
    initialize_floorplan -core_utilization $CORE_UTILIZATION -shape R -orientation N \
        -side_ratio [list $CORE_ASPECT_RATIO 1.0] -core_offset [list $CORE_OFFSET]
}
foreach spec $MACRO_PLACEMENTS {
    if {[llength $spec] != 4} { fatal_error "Bad MACRO_PLACEMENTS entry '$spec'; expected {instance x y orientation}." }
    lassign $spec inst x y orient
    set obj [get_cells -hierarchical -quiet $inst]
    if {[sizeof_collection $obj] != 1} { fatal_error "Configured macro instance '$inst' did not resolve uniquely." }
    set_cell_location $obj -coordinates [list $x $y] -orientation $orient
    if {$MACRO_FIX_PLACEMENT && [command_exists set_fixed_objects]} { set_fixed_objects $obj }
}
set macros [get_cells -hierarchical -quiet -filter "is_hard_macro==true"]
if {[sizeof_collection $macros] > 0} {
    if {$MACRO_HALO > 0} {
        require_command create_keepout_margin
        create_keepout_margin -type hard -outer [list $MACRO_HALO $MACRO_HALO $MACRO_HALO $MACRO_HALO] $macros
    }
    safe_report [file join $REPORT_DIR floorplan macros.rpt] { report_cell -physical_context }
    flow_info "Hard macros detected: review MACRO_CHANNEL=$MACRO_CHANNEL as the minimum planning objective between neighboring macros."
}
foreach spec $PLACEMENT_BLOCKAGES {
    if {[llength $spec] != 4} { fatal_error "Bad PLACEMENT_BLOCKAGES entry '$spec'; expected {name type boundary blocked_percentage}." }
    lassign $spec name type boundary blocked
    set args [list -name $name -type $type -boundary $boundary]
    if {$type eq "partial"} {
        require_nonempty $blocked "blocked_percentage for $name"
        lappend args -blocked_percentage $blocked
    }
    create_placement_blockage {*}$args
}
foreach spec $ROUTING_BLOCKAGES {
    if {[llength $spec] != 3} { fatal_error "Bad ROUTING_BLOCKAGES entry '$spec'; expected {name layer_list boundary}." }
    lassign $spec name layers boundary
    if {[llength $layers] == 0} { fatal_error "Routing blockage '$name' has no layers." }
    create_routing_blockage -name $name -layers $layers -boundary $boundary
}
if {$PIN_CONSTRAINT_FILE ne ""} {
    require_file $PIN_CONSTRAINT_FILE "pin-constraint file"
    if {![command_exists read_pin_constraints]} { fatal_error "PIN_CONSTRAINT_FILE configured but read_pin_constraints is unavailable." }
    read_pin_constraints -file_name $PIN_CONSTRAINT_FILE
}
if {$AUTO_PLACE_PINS} {
    if {[command_exists place_pins]} {
        if {[catch {place_pins -self} pinerr]} { flow_warning "Automatic pin placement failed/requires project review: $pinerr" }
    } else { flow_warning "place_pins unavailable in this ICC2 release." }
}
report_if_supported check_pin_placement [file join $REPORT_DIR floorplan pin_placement.rpt] -self
report_if_supported check_design [file join $REPORT_DIR floorplan check_design.rpt]
report_if_supported check_timing [file join $REPORT_DIR floorplan check_timing.rpt]
icc2_basic_reports floorplan
save_stage_block floorplan
write_status floorplan WARNING "Floorplan block generated. Review check_design/check_timing/pin/macro reports before treating it as physically signed off."
stage_complete "FLOORPLAN"
exit 0
