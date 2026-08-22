# =============================================================================
# Stage       : Placement and pre-CTS optimization
# Tool        : Synopsys IC Compiler II
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "PLACEMENT"
open_stage_block powerplan
place_opt
report_if_supported check_legality [file join $REPORT_DIR placement legality.rpt]
report_if_supported report_congestion [file join $REPORT_DIR placement congestion.rpt]
icc2_basic_reports placement
save_stage_block placement
write_status placement WARNING "place_opt completed; legality/congestion/timing reports were generated, but clean physical/timing status is not inferred without evaluating them."
stage_complete "PLACEMENT"
exit 0
