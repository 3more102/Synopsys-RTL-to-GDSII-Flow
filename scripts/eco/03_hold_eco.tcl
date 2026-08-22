# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 03_hold_eco.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/eco/03_hold_eco.tcl.
# =============================================================================
source [file join [file dirname [info script]] eco_common.tcl]
stage_banner "HOLD ECO"
open_stage_block [get_active_physical_stage]
set before [snapshot_eco_metrics hold_before]
set bsu [lindex $before 0]; set bho [lindex $before 1]
if {$bho ne "" && [expr {double($bho) >= 0.0}]} {
    flow_info "Worst hold slack is non-negative; hold ECO not required."
    write_status hold_eco PASS "No hold ECO required."
    exit 0
}
if {[llength $HOLD_CELLS] == 0} {
    flow_warning "HOLD_CELLS is empty. No guessed delay-cell insertion will be performed; route_opt will use library-legal optimization."
} elseif {[command_exists set_lib_cell_purpose]} {
    catch {set_lib_cell_purpose -include hold $HOLD_CELLS}
}
route_opt
set after [snapshot_eco_metrics hold_after]
set asu [lindex $after 0]; set aho [lindex $after 1]
if {[metric_ge $aho $bho] && ($bsu eq "" || [metric_ge $asu $bsu])} {
    save_stage_block eco_hold_accepted
    set_active_physical_stage eco_hold_accepted
    write_status hold_eco PASS "Candidate accepted: hold improved/non-regressed and setup did not worsen."
} else {
    write_status hold_eco WARNING "Candidate rejected; active block remains unchanged."
}
stage_complete "HOLD ECO"
exit 0
