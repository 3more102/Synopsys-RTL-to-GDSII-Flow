# =============================================================================
# Logical and physical library configuration.
# =============================================================================
source [file join [file dirname [info script]] project_config.tcl]
source [file join [file dirname [info script]] technology.tcl]
proc lib_env {name default} {
    if {[info exists ::env($name)] && $::env($name) ne ""} { return $::env($name) }
    return $default
}
set TARGET_LIBRARY [lib_env TARGET_LIBRARY ""]
set LINK_LIBRARIES [list]
if {$TARGET_LIBRARY ne ""} { lappend LINK_LIBRARIES $TARGET_LIBRARY }
set EXTRA_LINK_LIBS [lib_env EXTRA_LINK_LIBS ""]
if {$EXTRA_LINK_LIBS ne ""} {
    foreach f [split $EXTRA_LINK_LIBS :] { if {$f ne ""} { lappend LINK_LIBRARIES $f } }
}
set NDM_REFERENCE_LIBRARIES [list]
if {$STD_CELL_NDM ne ""} { lappend NDM_REFERENCE_LIBRARIES $STD_CELL_NDM }
set SYMBOL_LIBRARY [lib_env SYMBOL_LIBRARY ""]
set SYNTH_OPERATING_CONDITION [lib_env SYNTH_OPERATING_CONDITION ""]
