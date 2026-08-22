# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 05_tie_cells.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/placement/05_tie_cells.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "TIE CELL INSERTION"
open_stage_block placement
if {!$ENABLE_TIE_CELLS} { write_status tie_cells UNKNOWN "Tie-cell insertion disabled."; exit 0 }
if {[llength $TIE_HIGH_CELLS] == 0 || [llength $TIE_LOW_CELLS] == 0} { fatal_error "Configure TIE_HIGH_CELLS and TIE_LOW_CELLS before enabling tie insertion." }
foreach c [concat $TIE_HIGH_CELLS $TIE_LOW_CELLS] { if {[sizeof_collection [get_lib_cells -quiet $c]] == 0} { fatal_error "Tie lib cell not found: $c" } }
if {![command_exists add_tie_cells]} { fatal_error "add_tie_cells is unavailable in this ICC2 release; check installed command mapping/man page." }
set _const_pins [get_pins -hierarchical -quiet -filter "constant_value==0 || constant_value==1"]
if {[sizeof_collection $_const_pins] == 0} {
    flow_warning "No constant pins discovered via constant_value attribute; no tie cells inserted."
    write_status tie_cells WARNING "No constant pins matched."
    exit 0
}
add_tie_cells -objects $_const_pins -tie_high_lib_cells $TIE_HIGH_CELLS -tie_low_lib_cells $TIE_LOW_CELLS
report_if_supported check_legality [file join $REPORT_DIR placement tie_legality.rpt]
save_block
write_status tie_cells PASS "Configured tie cells inserted for discovered constant pins."
stage_complete "TIE CELL INSERTION"
exit 0
