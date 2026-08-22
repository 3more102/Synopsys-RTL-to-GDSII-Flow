# =============================================================================
# Stage       : Post-route signoff STA
# Tool        : Synopsys PrimeTime / PrimeTime SI
# =============================================================================
source [file join [file dirname [info script]] .. common load_config.tcl]
stage_banner "POST-ROUTE SIGNOFF STA"
set net [file join $NETLIST_DIR "${PROJECT_NAME}_postroute.v"]
set spef [file join $SPEF_DIR "${PROJECT_NAME}_postroute.spef"]
require_file $net "post-route netlist"
require_file $spef "post-route SPEF"
require_file $TARGET_LIBRARY "PrimeTime timing library"
set rpt [file join $REPORT_DIR signoff]; ensure_dir $rpt
set_app_var search_path [concat $search_path [list $LIB_DIR $CONSTRAINT_DIR]]
set_app_var link_path [concat * $LINK_LIBRARIES]
read_verilog $net
current_design $TOP_MODULE
link_design $TOP_MODULE
source [file join $CONSTRAINT_DIR top.sdc]
source [file join $PROJECT_ROOT scripts common path_groups.tcl]
read_parasitics -format spef $spef
if {[command_exists set_propagated_clock]} { set_propagated_clock [all_clocks] }
update_timing
safe_report [file join $rpt check_timing.rpt] { check_timing -verbose }
report_if_supported report_global_timing [file join $rpt summary.rpt]
safe_report [file join $rpt setup.rpt] [list report_timing -delay_type max -max_paths $MAX_PATHS -path_type full_clock_expanded -transition_time -capacitance -nets]
safe_report [file join $rpt hold.rpt] [list report_timing -delay_type min -max_paths $MAX_PATHS -path_type full_clock_expanded -transition_time -capacitance -nets]
safe_report [file join $rpt worst_setup.rpt] { report_timing -delay_type max -max_paths 1 -path_type full_clock_expanded }
safe_report [file join $rpt worst_hold.rpt] { report_timing -delay_type min -max_paths 1 -path_type full_clock_expanded }
report_if_supported report_constraint [file join $rpt constraints.rpt] -all_violators
report_if_supported report_units [file join $rpt units.rpt]
set PATH_GROUP_REPORT_DIR [file join $rpt path_groups]; ensure_dir $PATH_GROUP_REPORT_DIR
source [file join $PROJECT_ROOT scripts common report_path_groups.tcl]
report_if_supported report_clock [file join $rpt clocks.rpt]
report_if_supported report_clock_timing [file join $rpt clock_timing.rpt] -type summary
report_if_supported report_exceptions [file join $rpt exceptions.rpt] -all
report_if_supported report_case_analysis [file join $rpt case_analysis.rpt] -all
report_if_supported report_disable_timing [file join $rpt disabled_timing.rpt]
report_if_supported report_analysis_coverage [file join $rpt analysis_coverage.rpt] -status_details {untested violated}
report_if_supported report_si_bottleneck [file join $rpt si_bottleneck.rpt]
write_status signoff WARNING "PrimeTime completed extracted max/min STA; setup/hold PASS/FAIL is assigned only by the report evaluator."
write_checkpoint_marker [file join $CHECKPOINT_DIR signoff] signoff PASS
stage_complete "POST-ROUTE SIGNOFF STA"
exit 0
