# =============================================================================
# Stage       : ICC2 NDM design-library initialization
# Tool        : Synopsys IC Compiler II
# Run         : icc2_shell -f scripts/floorplan/00_create_design_lib.tcl
# =============================================================================
source [file join [file dirname [info script]] icc2_common.tcl]
stage_banner "ICC2 DESIGN INITIALIZATION"
set syn [file join $RESULT_DIR synthesis "${PROJECT_NAME}_syn.v"]
require_file $syn "synthesized netlist"
if {[llength $NDM_REFERENCE_LIBRARIES] == 0} { fatal_error "No NDM reference libraries configured." }
foreach l $NDM_REFERENCE_LIBRARIES { require_path $l "NDM reference library" }
set dlib [design_lib_path]
if {[file exists $dlib]} { fatal_error "Design library already exists: $dlib. Use distclean/rebuild deliberately instead of overwriting it." }
if {$TECH_FILE ne ""} {
    require_file $TECH_FILE "ICC2 technology file"
    create_lib -technology $TECH_FILE -ref_libs $NDM_REFERENCE_LIBRARIES $dlib
} else {
    create_lib -ref_libs $NDM_REFERENCE_LIBRARIES $dlib
}
open_lib $dlib
read_verilog -top $TOP_MODULE $syn
current_block $TOP_MODULE
link_block
if {$ENABLE_UPF} {
    set _upf [file join $POWER_INTENT_DIR top.upf]; require_file $_upf "UPF"
    if {![command_exists load_upf]} { fatal_error "UPF enabled but load_upf unavailable in ICC2." }
    load_upf $_upf
    if {[command_exists commit_upf]} { commit_upf } else { flow_warning "commit_upf unavailable; verify low-power flow for this release." }
}
source [file join $CONSTRAINT_DIR top.sdc]
source [file join $PROJECT_ROOT scripts common path_groups.tcl]
set _have_rcmax 0
set _have_rcmin 0
if {[command_exists read_parasitic_tech]} {
    if {$TLU_PLUS_MAX ne ""} {
        require_file $TLU_PLUS_MAX "TLU+ max"
        set args [list -tlup $TLU_PLUS_MAX -name rcmax]
        if {$TLU_PLUS_MAP ne ""} { require_file $TLU_PLUS_MAP "TLU+ map"; lappend args -layermap $TLU_PLUS_MAP }
        if {[catch {read_parasitic_tech {*}$args} rcerr]} { fatal_error "Failed to read max parasitic technology: $rcerr" }
        set _have_rcmax 1
    }
    if {$TLU_PLUS_MIN ne ""} {
        require_file $TLU_PLUS_MIN "TLU+ min"
        set args [list -tlup $TLU_PLUS_MIN -name rcmin]
        if {$TLU_PLUS_MAP ne ""} { require_file $TLU_PLUS_MAP "TLU+ map"; lappend args -layermap $TLU_PLUS_MAP }
        if {[catch {read_parasitic_tech {*}$args} rcerr]} { fatal_error "Failed to read min parasitic technology: $rcerr" }
        set _have_rcmin 1
    }
}
if {[command_exists set_parasitic_parameters]} {
    if {$_have_rcmax && $_have_rcmin} {
        set_parasitic_parameters -late_spec rcmax -early_spec rcmin
    } elseif {$_have_rcmax} {
        set_parasitic_parameters -late_spec rcmax
        flow_warning "Only max RC technology is configured; early/min RC analysis is incomplete."
    } elseif {$_have_rcmin} {
        set_parasitic_parameters -early_spec rcmin
        flow_warning "Only min RC technology is configured; late/max RC analysis is incomplete."
    }
}
report_if_supported report_parasitic_parameters [file join $REPORT_DIR init parasitic_parameters.rpt]
report_if_supported check_design [file join $REPORT_DIR init check_design.rpt]
report_if_supported check_timing [file join $REPORT_DIR init check_timing.rpt]
save_stage_block init
write_status init PASS "ICC2 design library created, mapped netlist linked, and init block saved."
stage_complete "ICC2 DESIGN INITIALIZATION"
exit 0
