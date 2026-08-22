# =============================================================================
# RTL file management.
# - Default: all .v/.sv files directly under rtl/ in deterministic order.
# - RTL_FILELIST: optional whitespace/newline file list path.
# - RTL_INCLUDE_DIRS: optional ':'-separated include-directory environment variable.
# - RTL_DEFINES: optional Tcl-list-style macro definitions, e.g. 'SYNTHESIS WIDTH=16'.
# =============================================================================
source [file join [file dirname [info script]] project_config.tcl]

set RTL_INCLUDE_DIRS [list $RTL_DIR]
if {[info exists ::env(RTL_INCLUDE_DIRS)] && $::env(RTL_INCLUDE_DIRS) ne ""} {
    set RTL_INCLUDE_DIRS [list]
    foreach d [split $::env(RTL_INCLUDE_DIRS) :] { if {$d ne ""} { lappend RTL_INCLUDE_DIRS [file normalize $d] } }
}
set RTL_DEFINES [list]
if {[info exists ::env(RTL_DEFINES)] && $::env(RTL_DEFINES) ne ""} { set RTL_DEFINES $::env(RTL_DEFINES) }

set RTL_FILES [list]
if {[info exists ::env(RTL_FILELIST)] && $::env(RTL_FILELIST) ne ""} {
    set _fl [file normalize $::env(RTL_FILELIST)]
    if {![file isfile $_fl]} { error "RTL_FILELIST not found: $_fl" }
    set _fh [open $_fl r]
    foreach line [split [read $_fh] "\n"] {
        set line [string trim $line]
        if {$line eq "" || [string match "#*" $line]} { continue }
        if {[file pathtype $line] eq "relative"} { set line [file join $PROJECT_ROOT $line] }
        lappend RTL_FILES [file normalize $line]
    }
    close $_fh
} else {
    set RTL_FILES [concat [glob -nocomplain -directory $RTL_DIR *.v] \
                          [glob -nocomplain -directory $RTL_DIR *.sv]]
    set RTL_FILES [lsort -unique $RTL_FILES]
}
