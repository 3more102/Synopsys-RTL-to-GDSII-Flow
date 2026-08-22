# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 04_post_cts_opt.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/cts/04_post_cts_opt.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "POST-CTS OPTIMIZATION"
open_stage_block post_cts
icc2_basic_reports post_cts_before_opt
clock_opt
icc2_basic_reports post_cts_opt
save_stage_block post_cts_opt
write_status post_cts_opt WARNING "Post-CTS optimization completed; closure remains report-driven."
stage_complete "POST-CTS OPTIMIZATION"
exit 0
