# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : debug_transition.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/debug/debug_transition.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
open_stage_block [get_active_physical_stage]
report_if_supported report_constraint [file join $REPORT_DIR debug max_transition.rpt] -max_transition -all_violators
report_if_supported report_constraint [file join $REPORT_DIR debug max_capacitance.rpt] -max_capacitance -all_violators
exit 0
