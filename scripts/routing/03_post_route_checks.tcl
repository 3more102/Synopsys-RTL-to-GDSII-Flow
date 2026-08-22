# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 03_post_route_checks.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/routing/03_post_route_checks.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "POST-ROUTE CHECKS"
open_stage_block post_route
report_if_supported check_routes [file join $REPORT_DIR post_route check_routes.rpt]
report_if_supported check_legality [file join $REPORT_DIR post_route legality.rpt]
report_if_supported report_congestion [file join $REPORT_DIR post_route congestion.rpt]
report_if_supported report_timing [file join $REPORT_DIR post_route setup.rpt] -delay_type max -max_paths 100
report_if_supported report_timing [file join $REPORT_DIR post_route hold.rpt] -delay_type min -max_paths 100
stage_complete "POST-ROUTE CHECKS"
exit 0
