# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : debug_congestion.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/debug/debug_congestion.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
open_stage_block [get_active_physical_stage]
report_if_supported report_congestion [file join $REPORT_DIR debug congestion.rpt]
report_if_supported report_utilization [file join $REPORT_DIR debug utilization.rpt]
exit 0
