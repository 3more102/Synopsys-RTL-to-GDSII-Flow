# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 02_lvs_setup.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/physical_verification/02_lvs_setup.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. common load_config.tcl]
stage_banner "LVS PREPARATION"
set net [file join $NETLIST_DIR "${PROJECT_NAME}_postroute.v"]
require_file $net "post-route netlist"
set gds [file join $GDS_DIR "${PROJECT_NAME}.gds"]
if {![file isfile $gds]} { flow_warning "GDS is not present yet; LVS cannot run until stream-out exists." }
write_text [file join $REPORT_DIR physical lvs_inputs.txt] "layout=$gds\nsource=$net\nstatus=UNKNOWN\nreason=Foundry-qualified LVS deck/runset is required.\n"
write_status lvs UNKNOWN "Foundry-qualified LVS deck/runset not configured."
stage_complete "LVS PREPARATION"
exit 0
