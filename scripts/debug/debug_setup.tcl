# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : debug_setup.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/debug/debug_setup.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
open_stage_block [get_active_physical_stage]
set d [file join $REPORT_DIR debug]; ensure_dir $d
report_if_supported report_timing [file join $d setup_detail.rpt] -delay_type max -max_paths 50 -path_type full_clock_expanded -transition_time -capacitance -nets
exit 0
