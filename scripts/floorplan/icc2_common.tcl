# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : icc2_common.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/floorplan/icc2_common.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. common load_config.tcl]
proc design_lib_path {} { global DATABASE_DIR PROJECT_NAME; return [file join $DATABASE_DIR "${PROJECT_NAME}.dlib"] }
proc open_stage_block {stage} {
    global TOP_MODULE
    set lib [design_lib_path]
    require_path $lib "ICC2 design library"
    open_lib $lib
    open_block "${TOP_MODULE}/${stage}"
    current_block
}
proc save_stage_block {stage} {
    global TOP_MODULE CHECKPOINT_DIR
    save_block -as "${TOP_MODULE}/${stage}"
    write_checkpoint_marker [file join $CHECKPOINT_DIR $stage] $stage COMPLETE
}
proc active_stage_file {} { global CHECKPOINT_DIR; return [file join $CHECKPOINT_DIR active_physical_block.txt] }
proc get_active_physical_stage {} {
    set f [active_stage_file]
    if {[file isfile $f]} {
        set h [open $f r]; set v [string trim [read $h]]; close $h
        if {$v ne ""} { return $v }
    }
    return final_route
}
proc set_active_physical_stage {stage} { write_text [active_stage_file] $stage }
proc icc2_basic_reports {stage} {
    global REPORT_DIR
    set d [file join $REPORT_DIR $stage]; ensure_dir $d
    report_if_supported report_qor [file join $d qor.rpt]
    report_if_supported report_design [file join $d design.rpt]
    report_if_supported report_utilization [file join $d utilization.rpt]
    report_if_supported report_units [file join $d units.rpt]
    report_if_supported report_clock [file join $d clocks.rpt]
    report_if_supported report_clock_timing [file join $d clock_timing.rpt] -type summary
    report_if_supported report_placement [file join $d placement.rpt]
    report_if_supported report_port [file join $d ports.rpt]
    report_if_supported report_cell [file join $d cells.rpt]
    report_if_supported report_global_timing [file join $d global_timing.rpt]
    report_if_supported report_timing [file join $d setup.rpt] -delay_type max -max_paths 100
    report_if_supported report_timing [file join $d hold.rpt] -delay_type min -max_paths 100
}
