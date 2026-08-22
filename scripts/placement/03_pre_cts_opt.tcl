# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 03_pre_cts_opt.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/placement/03_pre_cts_opt.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "PRE-CTS OPTIMIZATION"
open_stage_block placement
icc2_basic_reports pre_cts_before
place_opt
report_if_supported check_legality [file join $REPORT_DIR pre_cts legality.rpt]
report_if_supported report_congestion [file join $REPORT_DIR pre_cts congestion.rpt]
icc2_basic_reports pre_cts
save_stage_block pre_cts
write_status pre_cts WARNING "Incremental pre-CTS optimization completed; QoR/DRC reports must prove closure."
stage_complete "PRE-CTS OPTIMIZATION"
exit 0
