# =============================================================================
# Stage       : Vectorless post-layout power estimation
# Tool        : Synopsys PrimeTime PX capable shell
# =============================================================================
source [file join [file dirname [info script]] .. common load_config.tcl]
stage_banner "VECTORLESS POWER"
set net [file join $NETLIST_DIR "${PROJECT_NAME}_postroute.v"]
set spef [file join $SPEF_DIR "${PROJECT_NAME}_postroute.spef"]
require_file $net "post-route netlist"; require_file $spef "post-route SPEF"; require_file $TARGET_LIBRARY "power/timing library"
set rpt [file join $REPORT_DIR power]; ensure_dir $rpt
set_app_var link_path [concat * $LINK_LIBRARIES]
read_verilog $net; current_design $TOP_MODULE; link_design $TOP_MODULE
source [file join $CONSTRAINT_DIR top.sdc]
read_parasitics -format spef $spef
if {[command_exists set_power_analysis_mode]} { catch {set_power_analysis_mode averaged} }
if {[command_exists set_switching_activity]} {
    catch {set_switching_activity -static_probability 0.5 -toggle_rate 0.1 [get_nets -hierarchical *]}
}
if {[command_exists update_power]} { update_power } else { flow_warning "update_power unavailable; PrimeTime PX license may not be active." }
if {![report_if_supported report_power [file join $rpt vectorless_power.rpt] -hierarchy]} {
    write_status power UNKNOWN "PrimeTime PX report_power unavailable."
    fatal_error "Vectorless power report could not be generated."
}
write_status power PASS "Vectorless estimated power report generated; this is not measured silicon power."
stage_complete "VECTORLESS POWER"
exit 0
