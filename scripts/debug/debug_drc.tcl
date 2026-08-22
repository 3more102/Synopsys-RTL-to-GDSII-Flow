# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : debug_drc.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/debug/debug_drc.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
open_stage_block [get_active_physical_stage]
report_if_supported check_routes [file join $REPORT_DIR debug routing_drc.rpt]
report_if_supported check_pg_drc [file join $REPORT_DIR debug pg_drc.rpt]
exit 0
