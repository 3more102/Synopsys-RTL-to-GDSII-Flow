# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : path_groups.tcl
# Tool        : Synopsys shell / Tcl helper
# Description : Automation component for scripts/common/path_groups.tcl.
# =============================================================================
if {[command_exists group_path]} {
    if {[catch {
        set _regs [all_registers]
        set _ins [all_inputs]
        set _outs [all_outputs]
        if {[sizeof_collection $_regs] > 0} {
            group_path -name REG2REG -from $_regs -to $_regs
            if {[sizeof_collection $_ins] > 0} { group_path -name IN2REG -from $_ins -to $_regs }
            if {[sizeof_collection $_outs] > 0} { group_path -name REG2OUT -from $_regs -to $_outs }
        }
        if {[sizeof_collection $_ins] > 0 && [sizeof_collection $_outs] > 0} { group_path -name IN2OUT -from $_ins -to $_outs }
    } _pgerr]} { flow_warning "Path-group creation was partially skipped: $_pgerr" }
}
