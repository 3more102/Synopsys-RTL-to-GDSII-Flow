# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 04_spare_cells.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/placement/04_spare_cells.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "SPARE CELL INSERTION"
open_stage_block placement
if {!$ENABLE_SPARE_CELLS} { write_status spares UNKNOWN "Spare-cell insertion disabled."; exit 0 }
if {[llength $SPARE_CELLS] == 0 || $SPARE_NUM_INSTANCES <= 0} { fatal_error "Enable spare cells only after SPARE_CELLS and SPARE_NUM_INSTANCES are configured." }
foreach c $SPARE_CELLS { if {[sizeof_collection [get_lib_cells -quiet $c]] == 0} { fatal_error "Spare lib cell not found: $c" } }
add_spare_cells -cell_name SPARE -lib_cell $SPARE_CELLS -num_instances $SPARE_NUM_INSTANCES
set _spares [get_cells -hierarchical -quiet -filter "is_spare_cell==true"]
if {[sizeof_collection $_spares] > 0 && [command_exists place_eco_cells]} { place_eco_cells -legalize_only -cells $_spares }
report_if_supported check_legality [file join $REPORT_DIR placement spares_legality.rpt]
save_block
write_status spares PASS "Configured spare cells inserted and legalized."
stage_complete "SPARE CELL INSERTION"
exit 0
