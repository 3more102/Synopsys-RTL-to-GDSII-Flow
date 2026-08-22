# =============================================================================
# Optional tap/endcap insertion. No library names are guessed.
# Tool: Synopsys ICC2
# =============================================================================
source [file join [file dirname [info script]] icc2_common.tcl]
stage_banner "PHYSICAL-ONLY CELLS"
open_stage_block floorplan
proc assert_lib_cells {cells label} {
    foreach c $cells {
        if {[sizeof_collection [get_lib_cells -quiet $c]] == 0} { fatal_error "$label library cell not found: $c" }
    }
}
if {!$ENABLE_TAP_ENDCAP} {
    write_status physical_only UNKNOWN "Tap/endcap insertion disabled until legal PDK cell references and spacing are configured."
    flow_warning "Tap/endcap insertion disabled."
    exit 0
}
assert_lib_cells $TAP_CELLS TAP
assert_lib_cells $ENDCAP_CELLS ENDCAP
if {[llength $TAP_CELLS] != 1} { fatal_error "Exactly one TAP_CELLS reference is required by create_tap_cells." }
require_nonempty $TAP_DISTANCE TAP_DISTANCE
if {[llength $ENDCAP_CELLS] < 2} { fatal_error "Configure ENDCAP_CELLS with at least left and right boundary cells." }
create_boundary_cells -left_boundary_cell [lindex $ENDCAP_CELLS 0] -right_boundary_cell [lindex $ENDCAP_CELLS 1] -prefix ENDCAP
create_tap_cells -lib_cell [lindex $TAP_CELLS 0] -distance $TAP_DISTANCE -pattern stagger -prefix TAPCELL
report_if_supported check_boundary_cells [file join $REPORT_DIR floorplan boundary_cells.rpt]
report_if_supported check_legality [file join $REPORT_DIR floorplan physical_only_legality.rpt]
save_block
write_status physical_only PASS "Configured tap/endcap cells inserted into the floorplan block."
stage_complete "PHYSICAL-ONLY CELLS"
exit 0
