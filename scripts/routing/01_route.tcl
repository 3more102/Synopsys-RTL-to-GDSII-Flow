# =============================================================================
# Stage       : Signal routing
# Tool        : Synopsys IC Compiler II
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "ROUTING"
open_stage_block post_cts_opt
if {$MIN_ROUTING_LAYER ne "" && $MAX_ROUTING_LAYER ne "" && [command_exists set_ignored_layers]} {
    set_ignored_layers -min_routing_layer $MIN_ROUTING_LAYER -max_routing_layer $MAX_ROUTING_LAYER
}
route_auto
report_if_supported check_routes [file join $REPORT_DIR route route_status.rpt]
report_if_supported report_congestion [file join $REPORT_DIR route congestion.rpt]
icc2_basic_reports route
save_stage_block route
write_status route WARNING "route_auto completed. Routing cleanliness is determined only from check_routes/DRC evidence."
stage_complete "ROUTING"
exit 0
