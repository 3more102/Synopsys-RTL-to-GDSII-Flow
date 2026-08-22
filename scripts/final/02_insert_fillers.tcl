# =============================================================================
# Optional chip-finishing filler/decap insertion after routing.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "FILLER / DECAP INSERTION"
open_stage_block [get_active_physical_stage]
set _did 0
if {$ENABLE_FILLERS} {
    if {[llength $FILLER_CELLS] == 0} { fatal_error "ENABLE_FILLERS=1 but FILLER_CELLS is empty." }
    foreach c $FILLER_CELLS { if {[sizeof_collection [get_lib_cells -quiet $c]] == 0} { fatal_error "Filler lib cell not found: $c" } }
    create_stdcell_fillers -lib_cells $FILLER_CELLS -continue_on_error
    set _did 1
}
if {$ENABLE_DECAPS} {
    if {[llength $DECAP_CELLS] == 0} { fatal_error "ENABLE_DECAPS=1 but DECAP_CELLS is empty." }
    foreach c $DECAP_CELLS { if {[sizeof_collection [get_lib_cells -quiet $c]] == 0} { fatal_error "Decap lib cell not found: $c" } }
    create_stdcell_fillers -lib_cells $DECAP_CELLS -continue_on_error
    set _did 1
}
if {!$_did} {
    write_status fillers UNKNOWN "Filler/decap insertion disabled until legal physical-only references are configured."
    flow_warning "No filler/decap insertion requested."
    exit 0
}
if {[command_exists connect_pg_net]} { connect_pg_net -all_blocks -automatic }
if {[command_exists remove_stdcell_fillers_with_violation]} { remove_stdcell_fillers_with_violation }
report_if_supported check_routes [file join $REPORT_DIR final filler_route_check.rpt]
report_if_supported check_legality [file join $REPORT_DIR final filler_legality.rpt]
save_stage_block chipfinish
set_active_physical_stage chipfinish
write_status fillers PASS "Configured filler/decap cells inserted and chipfinish block promoted."
stage_complete "FILLER / DECAP INSERTION"
exit 0
