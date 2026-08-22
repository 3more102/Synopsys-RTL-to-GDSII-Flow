# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 02_setup_eco.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/eco/02_setup_eco.tcl.
# =============================================================================
source [file join [file dirname [info script]] eco_common.tcl]
stage_banner "SETUP ECO"
open_stage_block [get_active_physical_stage]
set before [snapshot_eco_metrics setup_before]
set bsu [lindex $before 0]; set bho [lindex $before 1]
if {$bsu ne "" && [expr {double($bsu) >= 0.0}]} {
    flow_info "Worst setup slack is non-negative; setup ECO not required."
    write_status setup_eco PASS "No setup ECO required."
    exit 0
}
route_opt
set after [snapshot_eco_metrics setup_after]
set asu [lindex $after 0]; set aho [lindex $after 1]
if {[metric_ge $asu $bsu] && ($bho eq "" || [metric_ge $aho $bho])} {
    save_stage_block eco_setup_accepted
    set_active_physical_stage eco_setup_accepted
    write_status setup_eco PASS "Candidate accepted: setup did not regress and hold did not worsen."
} else {
    write_status setup_eco WARNING "Candidate rejected; active block remains unchanged."
}
stage_complete "SETUP ECO"
exit 0
