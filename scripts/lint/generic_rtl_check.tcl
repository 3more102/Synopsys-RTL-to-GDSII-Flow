# =============================================================================
# Project     : MIPS_16 ASIC Flow
# Stage       : RTL sanity / lint-like checks
# Tool        : Synopsys Design Compiler
# Run         : dc_shell -f scripts/lint/generic_rtl_check.tcl
# =============================================================================
source [file join [file dirname [info script]] .. common load_config.tcl]
stage_banner "RTL SANITY CHECK"
set_app_var search_path [concat $search_path [list $RTL_DIR $LIB_DIR]]
set_app_var target_library [list $TARGET_LIBRARY]
set_app_var link_library [concat * $LINK_LIBRARIES]
source [file join $PROJECT_ROOT scripts common read_rtl.tcl]
set rpt [file join $REPORT_DIR lint]; ensure_dir $rpt
safe_report [file join $rpt check_design.rpt] { check_design -summary }
safe_report [file join $rpt check_design_verbose.rpt] { check_design }
report_if_supported report_hierarchy [file join $rpt hierarchy.rpt]
report_if_supported report_reference [file join $rpt references.rpt]
report_if_supported report_resources [file join $rpt resources.rpt]
report_if_supported report_design [file join $rpt design.rpt]
write_status lint WARNING "RTL analyzed, elaborated and linked. Structural cleanliness is not claimed until check_design reports are reviewed; CDC/RDC require dedicated analysis."
write_checkpoint_marker [file join $CHECKPOINT_DIR lint] lint PASS
stage_complete "RTL SANITY CHECK"
exit 0
