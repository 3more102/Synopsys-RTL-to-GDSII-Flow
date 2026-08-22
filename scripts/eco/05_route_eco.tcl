# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 05_route_eco.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/eco/05_route_eco.tcl.
# =============================================================================
source [file join [file dirname [info script]] eco_common.tcl]
stage_banner "ECO ROUTING"
open_stage_block [get_active_physical_stage]
route_opt
report_if_supported check_routes [file join $REPORT_DIR eco eco_route_check.rpt]
save_stage_block eco_routed
write_status eco_route PASS "ECO route optimization completed; not promoted until verification."
stage_complete "ECO ROUTING"
exit 0
