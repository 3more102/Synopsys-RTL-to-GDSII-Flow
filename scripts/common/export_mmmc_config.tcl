# =============================================================================
# Tool        : tclsh
# Description : Exports the Tcl-native CORNERS/MODES/SCENARIOS dictionaries as
#               tab-separated records for license-free structural validation.
# =============================================================================
set _here [file normalize [file dirname [info script]]]
set PROJECT_ROOT [file normalize [file join $_here .. ..]]
source [file join $PROJECT_ROOT config project_config.tcl]
source [file join $PROJECT_ROOT config corners.tcl]
source [file join $PROJECT_ROOT config modes.tcl]
source [file join $PROJECT_ROOT config scenarios.tcl]
proc clean_field {s} { return [string map [list "\t" " " "\n" " "] $s] }
foreach name [lsort [dict keys $CORNERS]] {
    set d [dict get $CORNERS $name]
    set purpose [expr {[dict exists $d purpose] ? [dict get $d purpose] : ""}]
    set lib [expr {[dict exists $d lib] ? [dict get $d lib] : ""}]
    set rc [expr {[dict exists $d rc] ? [dict get $d rc] : ""}]
    puts "CORNER\t[clean_field $name]\t[clean_field $purpose]\t[clean_field $rc]\t[clean_field $lib]"
}
foreach name [lsort [dict keys $MODES]] {
    set d [dict get $MODES $name]
    set enabled [expr {[dict exists $d enabled] ? [dict get $d enabled] : 0}]
    set sdc [expr {[dict exists $d sdc] ? [dict get $d sdc] : ""}]
    puts "MODE\t[clean_field $name]\t$enabled\t[clean_field $sdc]"
}
foreach name [lsort [dict keys $SCENARIOS]] {
    set d [dict get $SCENARIOS $name]
    set enabled [expr {[dict exists $d enabled] ? [dict get $d enabled] : 0}]
    set mode [expr {[dict exists $d mode] ? [dict get $d mode] : ""}]
    set corner [expr {[dict exists $d corner] ? [dict get $d corner] : ""}]
    puts "SCENARIO\t[clean_field $name]\t$enabled\t[clean_field $mode]\t[clean_field $corner]"
}
