# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : debug_fanout.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/debug/debug_fanout.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
open_stage_block [get_active_physical_stage]
if {[command_exists report_net_fanout]} { report_if_supported report_net_fanout [file join $REPORT_DIR debug fanout.rpt] -threshold $MAX_FANOUT } else { report_if_supported report_constraint [file join $REPORT_DIR debug fanout.rpt] -max_fanout -all_violators }
exit 0
