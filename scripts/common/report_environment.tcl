# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : report_environment.tcl
# Tool        : Synopsys shell / Tcl helper
# Description : Automation component for scripts/common/report_environment.tcl.
# =============================================================================
source [file join [file dirname [info script]] load_config.tcl]
stage_banner "RUN MANIFEST"
set out [file join $REPORT_DIR run_manifest.txt]
set lines [list \
    "Project: $PROJECT_NAME" \
    "Top: $TOP_MODULE" \
    "Technology: $TECHNOLOGY" \
    "Process: $PROCESS_NODE" \
    "Flow: $FLOW_TYPE" \
    "Date: [timestamp]" \
    "Project root: $PROJECT_ROOT" \
    "Target library: $TARGET_LIBRARY" \
    "NDM libraries: $NDM_REFERENCE_LIBRARIES" \
    "Technology file: $TECH_FILE" \
    "TLU+ max: $TLU_PLUS_MAX" \
    "TLU+ min: $TLU_PLUS_MIN"]
write_text $out [join $lines "\n"]
flow_info "Wrote $out"
stage_complete "RUN MANIFEST"
exit 0
