# =============================================================================
# Stage       : RTL-to-synthesis logical equivalence
# Tool        : Synopsys Formality
# Run         : fm_shell -f scripts/formal/02_rtl_vs_synth.tcl
# =============================================================================
source [file join [file dirname [info script]] 01_formality_setup.tcl]
stage_banner "FORMAL EQUIVALENCE"
set rpt [file join $REPORT_DIR formal]; ensure_dir $rpt
if {[file isfile $SVF_FILE] && [command_exists set_svf]} { set_svf $SVF_FILE }
read_db $TARGET_LIBRARY
set _vcs_opts ""
foreach d $RTL_INCLUDE_DIRS { append _vcs_opts " +incdir+$d" }
foreach d $RTL_DEFINES { append _vcs_opts " +define+$d" }
foreach f $RTL_FILES {
    if {[string equal -nocase [file extension $f] ".sv"]} {
        if {![command_exists read_sverilog]} { fatal_error "SystemVerilog RTL present but read_sverilog is unavailable in Formality." }
        read_sverilog -container r -libname WORK -vcs $_vcs_opts $f
    } else {
        read_verilog -container r -libname WORK -vcs $_vcs_opts $f
    }
}
set_top r:/WORK/$TOP_MODULE
read_verilog -container i -libname WORK -netlist $SYN_NETLIST
set_top i:/WORK/$TOP_MODULE
match
report_if_supported report_unmatched_points [file join $rpt unmatched.rpt]
report_if_supported report_matched_points [file join $rpt match.rpt]
set ok [verify]
report_if_supported report_failing_points [file join $rpt failing_points.rpt]
report_if_supported report_aborted_points [file join $rpt aborted_points.rpt]
report_if_supported report_not_verified [file join $rpt not_verified.rpt]
report_if_supported report_guidance [file join $rpt guidance.rpt] -summary
write_text [file join $rpt verification.rpt] "verify_return=$ok\n"
if {$ok != 1} {
    write_status formal FAIL "Formality verify returned failure/non-equivalence. Inspect failing/unmatched/aborted points."
    catch {save_session -replace [file join $rpt "${PROJECT_NAME}_failing"]}
    fatal_error "Formality equivalence did not pass." 3
}
write_status formal PASS "Formality verify returned 1 (equivalent)."
write_checkpoint_marker [file join $CHECKPOINT_DIR formal] formal PASS
stage_complete "FORMAL EQUIVALENCE"
exit 0
