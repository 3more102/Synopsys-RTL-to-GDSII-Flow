# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : debug_clock.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/debug/debug_clock.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
open_stage_block [get_active_physical_stage]
report_if_supported report_clock_timing [file join $REPORT_DIR debug clock_timing.rpt] -type summary
report_if_supported report_clock_tree [file join $REPORT_DIR debug clock_tree.rpt]
exit 0
