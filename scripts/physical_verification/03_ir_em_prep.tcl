# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 03_ir_em_prep.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/physical_verification/03_ir_em_prep.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "IR/EM PREPARATION"
open_stage_block [get_active_physical_stage]
set d [file join $REPORT_DIR physical]; ensure_dir $d
report_if_supported check_pg_connectivity [file join $d ir_em_pg_connectivity.rpt]
report_if_supported check_pg_drc [file join $d ir_em_pg_drc.rpt]
write_text [file join $d ir_em_status.txt] "STATUS: UNKNOWN\nPrimeRail/RedHawk analysis was not fabricated. Supply voltage/current/activity and qualified technology models are required."
write_status ir_em UNKNOWN "Prepared PG evidence only; no IR-drop/EM engine run."
stage_complete "IR/EM PREPARATION"
exit 0
