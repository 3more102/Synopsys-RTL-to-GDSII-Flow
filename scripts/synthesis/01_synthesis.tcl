# =============================================================================
# Project     : MIPS_16 ASIC Flow
# Stage       : Logic synthesis
# Tool        : Synopsys Design Compiler / DC Ultra
# Run         : dc_shell -f scripts/synthesis/01_synthesis.tcl
# =============================================================================
source [file join [file dirname [info script]] .. common load_config.tcl]
stage_banner "SYNTHESIS"
require_file $TARGET_LIBRARY "target .db library"
validate_file_list $RTL_FILES RTL
set out [file join $RESULT_DIR synthesis]; ensure_dir $out
set rpt [file join $REPORT_DIR synthesis]; ensure_dir $rpt
set svf [file join $out "${PROJECT_NAME}.svf"]
set_app_var search_path [concat $search_path $RTL_INCLUDE_DIRS [list $RTL_DIR $LIB_DIR $CONSTRAINT_DIR]]
set_app_var target_library [list $TARGET_LIBRARY]
set_app_var link_library [concat * $LINK_LIBRARIES]
if {$SYMBOL_LIBRARY ne ""} { set_app_var symbol_library [list $SYMBOL_LIBRARY] }
if {[command_exists set_svf]} { set_svf $svf }
source [file join $PROJECT_ROOT scripts common read_rtl.tcl]
if {$ENABLE_UPF} {
    set _upf [file join $POWER_INTENT_DIR top.upf]; require_file $_upf "UPF"
    if {[command_exists load_upf]} { load_upf $_upf } else { fatal_error "UPF enabled but load_upf unavailable in this DC shell/license." }
}
uniquify
if {$SYNTH_FLATTEN} { ungroup -all -flatten }
source [file join $CONSTRAINT_DIR top.sdc]
if {$SYNTH_OPERATING_CONDITION ne ""} { set_operating_conditions $SYNTH_OPERATING_CONDITION }
if {[catch {
    set _regs [all_registers]
    if {[sizeof_collection $_regs] > 0} {
        group_path -name REG2REG -from $_regs -to $_regs
        if {[sizeof_collection [all_inputs]] > 0}  { group_path -name IN2REG -from [all_inputs] -to $_regs }
        if {[sizeof_collection [all_outputs]] > 0} { group_path -name REG2OUT -from $_regs -to [all_outputs] }
    }
    if {[sizeof_collection [all_inputs]] > 0 && [sizeof_collection [all_outputs]] > 0} {
        group_path -name IN2OUT -from [all_inputs] -to [all_outputs]
    }
} err]} { flow_warning "Path grouping not fully applied: $err" }
safe_report [file join $rpt check_design_precompile.rpt] { check_design }
safe_report [file join $rpt check_timing_precompile.rpt] { check_timing }
if {$ENABLE_CLOCK_GATING} {
    if {$SYNTH_EFFORT eq "high"} { compile_ultra -gate_clock -timing_high_effort_script }
    else { compile_ultra -gate_clock }
} else {
    if {$SYNTH_EFFORT eq "high"} { compile_ultra -timing_high_effort_script }
    else { compile_ultra }
}
if {$ENABLE_INCREMENTAL_SYNTH} { catch {compile_ultra -incremental} inc_err; if {[info exists inc_err] && $inc_err ne ""} { flow_warning "Incremental synthesis note: $inc_err" } }
safe_report [file join $rpt check_design.rpt] { check_design }
safe_report [file join $rpt check_timing.rpt] { check_timing }
safe_report [file join $rpt timing_max.rpt] { report_timing -delay_type max -max_paths 100 -transition_time -capacitance -nets }
safe_report [file join $rpt timing_min.rpt] { report_timing -delay_type min -max_paths 100 -transition_time -capacitance -nets }
safe_report [file join $rpt timing_worst10.rpt] { report_timing -delay_type max -max_paths 10 }
safe_report [file join $rpt area.rpt] { report_area -hierarchy }
safe_report [file join $rpt power.rpt] { report_power -hierarchy }
safe_report [file join $rpt qor.rpt] { report_qor }
safe_report [file join $rpt constraints.rpt] { report_constraint -all_violators }
report_if_supported report_units [file join $rpt units.rpt]
set PATH_GROUP_REPORT_DIR [file join $rpt path_groups]; ensure_dir $PATH_GROUP_REPORT_DIR
source [file join $PROJECT_ROOT scripts common report_path_groups.tcl]
report_if_supported report_resources [file join $rpt resources.rpt]
report_if_supported report_reference [file join $rpt reference.rpt]
report_if_supported report_clock [file join $rpt clocks.rpt]
report_if_supported report_port [file join $rpt ports.rpt]
report_if_supported report_cell [file join $rpt cells.rpt]
report_if_supported report_net [file join $rpt nets.rpt]
report_if_supported report_design [file join $rpt design.rpt]
report_if_supported report_clock_gating [file join $rpt clock_gating.rpt]
write -format verilog -hierarchy -output [file join $out "${PROJECT_NAME}_syn.v"]
write -format ddc -hierarchy -output [file join $out "${PROJECT_NAME}_syn.ddc"]
write_sdc [file join $out "${PROJECT_NAME}_syn.sdc"]
if {[catch {write_sdf [file join $out "${PROJECT_NAME}_syn.sdf"]} sdf_err]} { flow_warning "Synthesis SDF not written: $sdf_err" }
write_status synthesis PASS "Design Compiler completed mapping and wrote mapped netlist/DDC/SDC. Timing closure must be judged from reports, not from stage execution alone."
write_checkpoint_marker [file join $CHECKPOINT_DIR synthesis] synthesis PASS
stage_complete "SYNTHESIS"
exit 0
