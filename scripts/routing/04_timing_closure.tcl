# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 04_timing_closure.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/routing/04_timing_closure.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "ITERATIVE POST-ROUTE CLOSURE"
open_stage_block post_route
set dir [file join $REPORT_DIR closure]; ensure_dir $dir
for {set i 1} {$i <= $ROUTE_TIMING_CLOSURE_ITERS} {incr i} {
    flow_info "Closure iteration $i"
    report_if_supported report_qor [file join $dir "iter_${i}_qor_before.rpt"]
    report_if_supported report_timing [file join $dir "iter_${i}_setup_before.rpt"] -delay_type max -max_paths 100
    report_if_supported report_timing [file join $dir "iter_${i}_hold_before.rpt"] -delay_type min -max_paths 100
    route_opt
    report_if_supported check_routes [file join $dir "iter_${i}_routes.rpt"]
    report_if_supported report_qor [file join $dir "iter_${i}_qor_after.rpt"]
}
save_stage_block final_route
write_status closure WARNING "Closure iterations executed. Python summary must confirm WNS/TNS/hold/DRC targets before declaring closure."
stage_complete "ITERATIVE POST-ROUTE CLOSURE"
exit 0
