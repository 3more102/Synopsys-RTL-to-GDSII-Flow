# =============================================================================
# Stage       : Clock tree synthesis / clock optimization
# Tool        : Synopsys IC Compiler II
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "CLOCK TREE SYNTHESIS"
open_stage_block pre_cts
source [file join [file dirname [info script]] 01_cts_setup.tcl]
clock_opt
report_if_supported report_clock_timing [file join $REPORT_DIR cts clock_timing.rpt] -type summary
report_if_supported report_clock_tree [file join $REPORT_DIR cts clock_tree.rpt]
icc2_basic_reports post_cts
save_stage_block post_cts
write_status cts WARNING "clock_opt completed; skew/latency/setup/hold reports must prove clock-tree quality."
stage_complete "CLOCK TREE SYNTHESIS"
exit 0
