# =============================================================================
# Stage       : Pre-layout static timing analysis
# Tool        : Synopsys PrimeTime
# Run         : pt_shell -f scripts/sta/01_prelayout_sta.tcl
# =============================================================================
source [file join [file dirname [info script]] .. common load_config.tcl]
stage_banner "PRE-LAYOUT STA"
set syn [file join $RESULT_DIR synthesis "${PROJECT_NAME}_syn.v"]
require_file $syn "synthesized netlist"
require_file $TARGET_LIBRARY "PrimeTime timing library"
set rpt [file join $REPORT_DIR presta]; ensure_dir $rpt
set_app_var search_path [concat $search_path [list $LIB_DIR $CONSTRAINT_DIR]]
set_app_var link_path [concat * $LINK_LIBRARIES]
read_verilog $syn
current_design $TOP_MODULE
link_design $TOP_MODULE
source [file join $CONSTRAINT_DIR top.sdc]
source [file join $PROJECT_ROOT scripts common path_groups.tcl]
update_timing
safe_report [file join $rpt check_timing.rpt] { check_timing -verbose }
report_if_supported report_global_timing [file join $rpt timing_summary.rpt]
safe_report [file join $rpt timing_setup.rpt] { report_timing -delay_type max -max_paths 100 -transition_time -capacitance -nets }
safe_report [file join $rpt timing_hold.rpt] { report_timing -delay_type min -max_paths 100 -transition_time -capacitance -nets }
safe_report [file join $rpt timing_worst_setup.rpt] { report_timing -delay_type max -max_paths 1 -path_type full_clock_expanded }
safe_report [file join $rpt timing_worst_hold.rpt] { report_timing -delay_type min -max_paths 1 -path_type full_clock_expanded }
report_if_supported report_clock [file join $rpt clocks.rpt]
report_if_supported report_clock_timing [file join $rpt clock_timing.rpt] -type summary
report_if_supported report_constraint [file join $rpt constraints.rpt] -all_violators
report_if_supported report_units [file join $rpt units.rpt]
set PATH_GROUP_REPORT_DIR [file join $rpt path_groups]; ensure_dir $PATH_GROUP_REPORT_DIR
source [file join $PROJECT_ROOT scripts common report_path_groups.tcl]
report_if_supported report_exceptions [file join $rpt exceptions.rpt] -all
report_if_supported report_case_analysis [file join $rpt case_analysis.rpt] -all
report_if_supported report_disable_timing [file join $rpt disabled_timing.rpt]
safe_report [file join $rpt unconstrained.rpt] { check_timing -verbose }
write_status presta PASS "PrimeTime linked the synthesized netlist and completed max/min timing analysis. Check WNS/TNS and unconstrained paths before interpreting timing as closed."
write_checkpoint_marker [file join $CHECKPOINT_DIR presta] presta PASS
stage_complete "PRE-LAYOUT STA"
exit 0
