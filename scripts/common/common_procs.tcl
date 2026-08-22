# =============================================================================
# Shared Tcl utilities for all Synopsys shells.
# =============================================================================
proc timestamp {} { return [clock format [clock seconds] -format "%Y-%m-%d %H:%M:%S"] }
proc flow_info {msg} { puts "INFO  [timestamp] : $msg" }
proc flow_warning {msg} { puts stderr "WARN  [timestamp] : $msg" }
proc fatal_error {msg {code 2}} { puts stderr "ERROR [timestamp] : $msg"; exit $code }
proc ensure_dir {d} { if {![file exists $d]} { file mkdir $d }; return [file normalize $d] }
proc require_file {f {why "required input"}} {
    if {$f eq ""} { fatal_error "$why is not configured." }
    if {![file isfile $f]} { fatal_error "$why not found: $f" }
    return [file normalize $f]
}
proc require_path {p {why "required path"}} {
    # NDM/design libraries can be represented as a file or directory depending on release/installation.
    if {$p eq ""} { fatal_error "$why is not configured." }
    if {![file exists $p]} { fatal_error "$why not found: $p" }
    return [file normalize $p]
}
proc require_dir {d {why "required directory"}} {
    if {$d eq "" || ![file isdirectory $d]} { fatal_error "$why not found: $d" }
    return [file normalize $d]
}
proc command_exists {name} { expr {[llength [info commands $name]] > 0} }
proc require_command {name} { if {![command_exists $name]} { fatal_error "Tool command '$name' is unavailable in this shell/release." } }
proc safe_report {outfile script_body} {
    file mkdir [file dirname $outfile]
    if {[catch {redirect -file $outfile $script_body} err]} {
        flow_warning "Report failed: $outfile -- $err"
        return 0
    }
    return 1
}
proc write_text {path text} { file mkdir [file dirname $path]; set f [open $path w]; puts $f $text; close $f }
proc append_text {path text} { file mkdir [file dirname $path]; set f [open $path a]; puts $f $text; close $f }
proc write_checkpoint_marker {dir stage status} {
    file mkdir $dir
    set path [file join $dir "${stage}.status"]
    write_text $path "stage=$stage\nstatus=$status\ntime=[timestamp]"
    return $path
}
proc stage_banner {name} {
    puts "============================================================"
    puts "Starting $name"
    puts "============================================================"
}
proc stage_complete {name} {
    puts "============================================================"
    puts "$name COMPLETE"
    puts "============================================================"
}
proc require_nonempty {value label} { if {$value eq ""} { fatal_error "$label is empty; configure it before this stage." } }
proc validate_file_list {files label} {
    if {[llength $files] == 0} { fatal_error "$label list is empty." }
    set seen [dict create]
    foreach f $files {
        require_file $f "$label file"
        set n [file normalize $f]
        if {[dict exists $seen $n]} { fatal_error "Duplicate $label file: $n" }
        dict set seen $n 1
    }
}
proc write_status {stage status detail} {
    global REPORT_DIR
    set dir [file join $REPORT_DIR status]
    file mkdir $dir
    write_text [file join $dir "${stage}.status"] "stage=$stage\nstatus=$status\ndetail=$detail\ntime=[timestamp]"
}
proc report_if_supported {cmd outfile args} {
    if {![command_exists $cmd]} { flow_warning "$cmd unsupported; $outfile not produced."; return 0 }
    return [safe_report $outfile [list $cmd {*}$args]]
}
