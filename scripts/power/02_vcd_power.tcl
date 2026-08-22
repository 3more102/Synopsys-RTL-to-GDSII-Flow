# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 02_vcd_power.tcl
# Tool        : Synopsys PrimeTime / PrimeTime PX
# Description : Automation component for scripts/power/02_vcd_power.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. common load_config.tcl]
stage_banner "VCD-BASED POWER"
set vcd [file join $SAIF_DIR "${PROJECT_NAME}.vcd"]
require_file $vcd "VCD activity file"
set net [file join $NETLIST_DIR "${PROJECT_NAME}_postroute.v"]
set spef [file join $SPEF_DIR "${PROJECT_NAME}_postroute.spef"]
require_file $net "post-route netlist"; require_file $spef "post-route SPEF"; require_file $TARGET_LIBRARY "power/timing library"
set_app_var link_path [concat * $LINK_LIBRARIES]
read_verilog $net; current_design $TOP_MODULE; link_design $TOP_MODULE
source [file join $CONSTRAINT_DIR top.sdc]; read_parasitics -format spef $spef
if {![command_exists read_vcd]} { fatal_error "read_vcd unavailable; PrimeTime PX activity flow not supported in this shell." }
if {$VCD_STRIP_PATH ne ""} { read_vcd $vcd -strip_path $VCD_STRIP_PATH } else { read_vcd $vcd }
if {[command_exists update_power]} { update_power }
report_if_supported report_power [file join $REPORT_DIR power vcd_power.rpt] -hierarchy
write_status vcd_power PASS "Post-layout power report generated using VCD switching activity."
stage_complete "VCD-BASED POWER"
exit 0
