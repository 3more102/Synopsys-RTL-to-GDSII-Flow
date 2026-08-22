# =============================================================================
# Stage       : Final logical/timing output writing from routed ICC2 block
# Tool        : Synopsys IC Compiler II
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "WRITE FINAL LOGICAL OUTPUTS"
open_stage_block [get_active_physical_stage]
set net [file join $NETLIST_DIR "${PROJECT_NAME}_postroute.v"]
set sdf [file join $SDF_DIR "${PROJECT_NAME}_postroute.sdf"]
set sdc [file join $FINAL_DIR "${PROJECT_NAME}_final.sdc"]
write_verilog $net
if {[command_exists write_sdf]} {
    if {[catch {write_sdf $sdf} e]} { flow_warning "Final SDF not generated: $e" }
} else { flow_warning "write_sdf unsupported in this ICC2 release; generate SDF from PrimeTime if required." }
if {[command_exists write_sdc]} { write_sdc $sdc } else { file copy -force [file join $CONSTRAINT_DIR top.sdc] $sdc }
require_file $net "final post-route netlist"
write_status final_outputs PASS "Final netlist written; SDF availability recorded by file existence."
stage_complete "WRITE FINAL LOGICAL OUTPUTS"
exit 0
