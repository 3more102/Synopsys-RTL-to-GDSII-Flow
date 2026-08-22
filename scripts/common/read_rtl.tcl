# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : read_rtl.tcl
# Tool        : Synopsys shell / Tcl helper
# Description : Automation component for scripts/common/read_rtl.tcl.
# =============================================================================
validate_file_list $RTL_FILES RTL
foreach d $RTL_INCLUDE_DIRS { require_dir $d "RTL include directory" }
if {[info exists search_path]} { set_app_var search_path [concat $search_path $RTL_INCLUDE_DIRS] }
set verilog_files [list]
set sverilog_files [list]
foreach f $RTL_FILES {
    switch -nocase -- [file extension $f] {
        .sv { lappend sverilog_files $f }
        .v  { lappend verilog_files $f }
        default { fatal_error "Unsupported RTL extension: $f" }
    }
}
set _analyze_opts [list]
if {[llength $RTL_DEFINES] > 0} { lappend _analyze_opts -define $RTL_DEFINES }
if {[llength $verilog_files]}  { analyze -format verilog   {*}${_analyze_opts} $verilog_files }
if {[llength $sverilog_files]} { analyze -format sverilog {*}${_analyze_opts} $sverilog_files }
elaborate $TOP_MODULE
current_design $TOP_MODULE
if {![link]} { fatal_error "Design linking failed after RTL elaboration." }
