# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 01_analyze_violations.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/eco/01_analyze_violations.tcl.
# =============================================================================
source [file join [file dirname [info script]] eco_common.tcl]
stage_banner "ECO ANALYSIS"
open_stage_block [get_active_physical_stage]
set m [snapshot_eco_metrics pre_eco]
report_if_supported check_routes [file join $REPORT_DIR eco pre_eco_routes.rpt]
write_status eco_analysis PASS "ECO baseline captured. No design modification performed."
stage_complete "ECO ANALYSIS"
exit 0
