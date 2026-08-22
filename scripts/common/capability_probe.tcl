# =============================================================================
# Tool        : Synopsys dc_shell / icc2_shell / pt_shell / fm_shell
# Description : Read-only release compatibility probe. Commands are detected
#               with Tcl info commands; no design is read and tested commands
#               are not executed.
# =============================================================================
proc json_escape {s} { regsub -all {\\} $s {\\\\} s; regsub -all {"} $s {\\"} s; regsub -all {\n} $s {\\n} s; return $s }
if {![info exists ::env(PROBE_OUTPUT)] || $::env(PROBE_OUTPUT) eq ""} { puts stderr "ERROR: PROBE_OUTPUT is required"; exit 2 }
set output $::env(PROBE_OUTPUT)
set kind [expr {[info exists ::env(PROBE_TOOL_KIND)] ? $::env(PROBE_TOOL_KIND) : "unknown"}]
set commands [expr {[info exists ::env(PROBE_COMMANDS)] ? $::env(PROBE_COMMANDS) : ""}]
set required [expr {[info exists ::env(PROBE_REQUIRED_COMMANDS)] ? $::env(PROBE_REQUIRED_COMMANDS) : ""}]
set version "UNKNOWN"
if {[llength [info commands get_app_var]] > 0} { catch {set version [get_app_var sh_product_version]} }
if {$version eq "UNKNOWN" && [info exists ::synopsys_program_name]} { set version $::synopsys_program_name }
file mkdir [file dirname $output]; set fh [open $output w]
puts $fh "{"; puts $fh "  \"schema_version\": 1,"; puts $fh "  \"tool_kind\": \"[json_escape $kind]\","; puts $fh "  \"tool_version\": \"[json_escape $version]\","; puts $fh "  \"status\": \"AVAILABLE\","; puts $fh "  \"commands\": {"
set first 1
foreach cmd $commands { if {!$first} { puts $fh "," }; set first 0; set supported [expr {[llength [info commands $cmd]] > 0 ? "true" : "false"}]; set is_required [expr {[lsearch -exact $required $cmd] >= 0 ? "true" : "false"}]; puts -nonewline $fh "    \"[json_escape $cmd]\": {\"supported\": $supported, \"required\": $is_required}" }
puts $fh ""; puts $fh "  }"; puts $fh "}"; close $fh
puts "Capability probe complete: $output"; exit 0
