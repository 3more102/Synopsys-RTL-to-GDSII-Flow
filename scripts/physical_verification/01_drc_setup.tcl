# =============================================================================
# Stage       : Physical verification / DRC preparation
# Tool        : ICC2 in-design checks; optional IC Validator signoff
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "DRC PREPARATION"
open_stage_block [get_active_physical_stage]
set d [file join $REPORT_DIR physical]; ensure_dir $d
report_if_supported check_routes [file join $d in_design_route_check.rpt]
report_if_supported check_pg_connectivity [file join $d pg_connectivity.rpt]
report_if_supported check_pg_drc [file join $d pg_drc.rpt]
if {!$ENABLE_ICV} {
    write_status drc UNKNOWN "ICV/foundry runset not enabled; only ICC2 in-design checks were executed."
} elseif {[command_exists signoff_check_drc]} {
    flow_warning "ICV integration is enabled, but foundry runset/deck variables must be added for the installed process before signoff_check_drc is launched."
    write_status drc UNKNOWN "ICV command exists, but no foundry-qualified runset was configured."
} else {
    write_status drc UNKNOWN "ICV integration command unavailable in this ICC2 shell."
}
stage_complete "DRC PREPARATION"
exit 0
