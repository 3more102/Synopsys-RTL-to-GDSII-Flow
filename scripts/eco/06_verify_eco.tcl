# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 06_verify_eco.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/eco/06_verify_eco.tcl.
# =============================================================================
source [file join [file dirname [info script]] eco_common.tcl]
stage_banner "ECO VERIFICATION"
open_stage_block [get_active_physical_stage]
snapshot_eco_metrics verify_eco
report_if_supported check_routes [file join $REPORT_DIR eco verify_routes.rpt]
report_if_supported check_legality [file join $REPORT_DIR eco verify_legality.rpt]
write_status eco_verify WARNING "Database checks completed. Re-run extraction, PrimeTime STA and Formality as applicable before final signoff."
stage_complete "ECO VERIFICATION"
exit 0
