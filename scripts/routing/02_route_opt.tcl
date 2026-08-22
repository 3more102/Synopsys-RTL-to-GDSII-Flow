# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 02_route_opt.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/routing/02_route_opt.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "ROUTE OPTIMIZATION"
open_stage_block route
route_opt
report_if_supported check_routes [file join $REPORT_DIR post_route route_status.rpt]
icc2_basic_reports post_route
save_stage_block post_route
write_status post_route WARNING "route_opt completed; timing/route reports must prove closure."
stage_complete "ROUTE OPTIMIZATION"
exit 0
