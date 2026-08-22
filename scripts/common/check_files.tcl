# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : check_files.tcl
# Tool        : Synopsys shell / Tcl helper
# Description : Automation component for scripts/common/check_files.tcl.
# =============================================================================
# Focused artifact validation utility. Source after load_config.tcl.
proc require_synthesis_outputs {} {
    global RESULT_DIR PROJECT_NAME
    require_file [file join $RESULT_DIR synthesis "${PROJECT_NAME}_syn.v"] "synthesized netlist"
    require_file [file join $RESULT_DIR synthesis "${PROJECT_NAME}_syn.sdc"] "synthesized SDC"
}
proc require_postroute_outputs {} {
    global NETLIST_DIR SPEF_DIR PROJECT_NAME CONSTRAINT_DIR
    require_file [file join $NETLIST_DIR "${PROJECT_NAME}_postroute.v"] "post-route netlist"
    require_file [file join $SPEF_DIR "${PROJECT_NAME}_postroute.spef"] "post-route SPEF"
    require_file [file join $CONSTRAINT_DIR top.sdc] "final timing constraints"
}
