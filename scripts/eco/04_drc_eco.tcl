# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 04_drc_eco.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/eco/04_drc_eco.tcl.
# =============================================================================
source [file join [file dirname [info script]] eco_common.tcl]
stage_banner "ROUTING DRC ECO"
open_stage_block [get_active_physical_stage]
report_if_supported check_routes [file join $REPORT_DIR eco drc_before.rpt]
route_opt
report_if_supported check_routes [file join $REPORT_DIR eco drc_after.rpt]
save_stage_block eco_drc_candidate
write_status drc_eco WARNING "Route repair candidate generated; inspect check_routes and foundry DRC separately before promotion."
stage_complete "ROUTING DRC ECO"
exit 0
