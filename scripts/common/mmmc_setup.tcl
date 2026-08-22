# =============================================================================
# Optional ICC2 MMMC infrastructure.
# Real PVT libraries / operating conditions / RC tech names must be supplied by the PDK.
# =============================================================================
source [file join [file dirname [info script]] load_config.tcl]
source [file join $PROJECT_ROOT config corners.tcl]
source [file join $PROJECT_ROOT config modes.tcl]
source [file join $PROJECT_ROOT config scenarios.tcl]
if {![command_exists create_mode] || ![command_exists create_corner] || ![command_exists create_scenario]} {
    fatal_error "MMMC setup requested in a shell without ICC2 mode/corner/scenario commands."
}
foreach mode [dict keys $MODES] {
    set md [dict get $MODES $mode]
    if {[dict get $md enabled]} {
        if {[sizeof_collection [get_modes -quiet $mode]] == 0} { create_mode $mode }
        current_mode $mode
        set sdc [dict get $md sdc]
        if {$sdc ne ""} { require_file $sdc "mode SDC"; read_sdc $sdc }
    }
}
foreach corner [dict keys $CORNERS] {
    set cd [dict get $CORNERS $corner]
    if {[sizeof_collection [get_corners -quiet $corner]] == 0} { create_corner $corner }
}
set enabled_count 0
foreach sc [dict keys $SCENARIOS] {
    set sd [dict get $SCENARIOS $sc]
    if {![dict get $sd enabled]} { continue }
    incr enabled_count
    set mode [dict get $sd mode]; set corner [dict get $sd corner]
    set lib [dict get [dict get $CORNERS $corner] lib]
    if {$lib eq ""} { fatal_error "Scenario $sc is enabled but corner $corner has no real PVT library configured." }
    if {[sizeof_collection [get_scenarios -quiet $sc]] == 0} { create_scenario -mode $mode -corner $corner -name $sc }
}
if {$enabled_count == 0} { flow_warning "No MMMC scenarios enabled; base flow remains single-mode/single-corner." }
report_if_supported report_modes [file join $REPORT_DIR mmmc modes.rpt]
report_if_supported report_corners [file join $REPORT_DIR mmmc corners.rpt]
report_if_supported report_scenarios [file join $REPORT_DIR mmmc scenarios.rpt]
