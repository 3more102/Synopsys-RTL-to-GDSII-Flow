# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 02_saif_power.tcl
# Tool        : Synopsys PrimeTime / PrimeTime PX
# Description : Automation component for scripts/power/02_saif_power.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. common load_config.tcl]
stage_banner "SAIF-BASED POWER"
set saif [file join $SAIF_DIR "${PROJECT_NAME}.saif"]
if {![file isfile $saif]} { write_status saif_power UNKNOWN "SAIF activity file absent."; fatal_error "SAIF not found: $saif" }
set net [file join $NETLIST_DIR "${PROJECT_NAME}_postroute.v"]
set spef [file join $SPEF_DIR "${PROJECT_NAME}_postroute.spef"]
require_file $net "post-route netlist"; require_file $spef "post-route SPEF"
set_app_var link_path [concat * $LINK_LIBRARIES]
read_verilog $net; current_design $TOP_MODULE; link_design $TOP_MODULE
source [file join $CONSTRAINT_DIR top.sdc]; read_parasitics -format spef $spef
if {![command_exists read_saif]} { fatal_error "read_saif unavailable; PrimeTime PX activity flow not supported in this shell." }
if {$SAIF_STRIP_PATH ne ""} { read_saif $saif -strip_path $SAIF_STRIP_PATH } else { read_saif $saif }
if {[command_exists update_power]} { update_power }
report_if_supported report_power [file join $REPORT_DIR power saif_power.rpt] -hierarchy
write_status saif_power PASS "Power report generated using SAIF activity plus extracted parasitics."
stage_complete "SAIF-BASED POWER"
exit 0
