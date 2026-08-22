# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 03_post_cts_reports.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/cts/03_post_cts_reports.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "POST-CTS REPORTS"
open_stage_block post_cts
report_if_supported report_clock_timing [file join $REPORT_DIR cts post_cts_clock_timing.rpt] -type summary
report_if_supported report_timing [file join $REPORT_DIR cts setup.rpt] -delay_type max -max_paths 100
report_if_supported report_timing [file join $REPORT_DIR cts hold.rpt] -delay_type min -max_paths 100
report_if_supported report_qor [file join $REPORT_DIR cts qor.rpt]
stage_complete "POST-CTS REPORTS"
exit 0
