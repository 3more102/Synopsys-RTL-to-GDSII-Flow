# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : discover_special_cells.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/debug/discover_special_cells.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
open_stage_block floorplan
set d [file join $REPORT_DIR debug]; ensure_dir $d
foreach pattern [list *TAP* *FILL* *DECAP* *END* *TIE* *CLK* *BUF* *INV*] {
    set out [file join $d "libcells_[string map {* STAR} $pattern].rpt"]
    if {[command_exists get_lib_cells]} { safe_report $out [list get_lib_cells -quiet "*/$pattern"] }
}
exit 0
