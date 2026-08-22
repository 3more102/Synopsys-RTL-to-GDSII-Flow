# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : eco_common.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/eco/eco_common.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
proc worst_slack {delay_type} {
    if {![command_exists get_timing_paths]} { return "" }
    set p [get_timing_paths -delay_type $delay_type -max_paths 1]
    if {[sizeof_collection $p] == 0} { return "" }
    return [get_attribute $p slack]
}
proc metric_ge {a b} {
    if {$a eq "" || $b eq ""} { return 0 }
    expr {double($a) >= double($b)}
}
proc snapshot_eco_metrics {tag} {
    global REPORT_DIR
    set d [file join $REPORT_DIR eco]; ensure_dir $d
    set su [worst_slack max]; set ho [worst_slack min]
    write_text [file join $d "${tag}.metrics"] "setup_worst_slack=$su\nhold_worst_slack=$ho\n"
    report_if_supported report_qor [file join $d "${tag}_qor.rpt"]
    report_if_supported report_timing [file join $d "${tag}_setup.rpt"] -delay_type max -max_paths 100
    report_if_supported report_timing [file join $d "${tag}_hold.rpt"] -delay_type min -max_paths 100
    return [list $su $ho]
}
