# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : debug_reset.tcl
# Tool        : Synopsys IC Compiler II / stage helper
# Description : Automation component for scripts/debug/debug_reset.tcl.
# =============================================================================
# Reset-net inventory. Synchrony/asynchrony cannot be proven from a name alone.
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
open_stage_block [get_active_physical_stage]
set d [file join $REPORT_DIR debug]; ensure_dir $d
set _rst [get_nets -hierarchical -quiet *reset*]
if {[sizeof_collection $_rst] == 0} { set _rst [get_nets -hierarchical -quiet *rst*] }
safe_report [file join $d reset_nets.rpt] { foreach_in_collection n $_rst { puts "[get_object_name $n] fanout=[sizeof_collection [all_fanout -flat -from $n -endpoints_only]]" } }
write_text [file join $d reset_classification_note.txt] "Reset names/connectivity are reported. Synchronous versus asynchronous reset semantics must be confirmed from RTL sequential sensitivity/control behavior; this flow does not guess from naming."
exit 0
