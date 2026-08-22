# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : report_path_groups.tcl
# Tool        : Synopsys shell / Tcl helper
# Description : Automation component for scripts/common/report_path_groups.tcl.
# =============================================================================
foreach _g {REG2REG IN2REG REG2OUT IN2OUT} {
    if {[command_exists report_timing]} {
        catch {redirect -file [file join $PATH_GROUP_REPORT_DIR "${_g}_setup.rpt"] { report_timing -group $_g -delay_type max -max_paths 50 }}
        catch {redirect -file [file join $PATH_GROUP_REPORT_DIR "${_g}_hold.rpt"]  { report_timing -group $_g -delay_type min -max_paths 50 }}
    }
}
