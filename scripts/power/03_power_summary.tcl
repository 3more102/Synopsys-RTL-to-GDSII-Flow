# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 03_power_summary.tcl
# Tool        : Synopsys PrimeTime / PrimeTime PX
# Description : Automation component for scripts/power/03_power_summary.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. common load_config.tcl]
set out [file join $REPORT_DIR power README.txt]
write_text $out "Power evidence files:\n- vectorless_power.rpt: estimated activity\n- saif_power.rpt: simulation-activity based when available\nNever label either as measured silicon power."
exit 0
