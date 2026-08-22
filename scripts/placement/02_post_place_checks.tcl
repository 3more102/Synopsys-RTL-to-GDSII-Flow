# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 02_post_place_checks.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/placement/02_post_place_checks.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "POST-PLACE CHECKS"
open_stage_block placement
report_if_supported check_legality [file join $REPORT_DIR placement post_place_legality.rpt]
report_if_supported report_congestion [file join $REPORT_DIR placement post_place_congestion.rpt]
report_if_supported report_timing [file join $REPORT_DIR placement post_place_setup.rpt] -delay_type max -max_paths 100
report_if_supported report_timing [file join $REPORT_DIR placement post_place_hold.rpt] -delay_type min -max_paths 100
stage_complete "POST-PLACE CHECKS"
exit 0
