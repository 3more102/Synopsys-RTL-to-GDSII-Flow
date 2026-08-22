# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : load_config.tcl
# Tool        : Synopsys shell / Tcl helper
# Description : Automation component for scripts/common/load_config.tcl.
# =============================================================================
# Load all shared configuration and utility procedures exactly once.
set _common_dir [file normalize [file dirname [info script]]]
set _root [file normalize [file join $_common_dir .. ..]]
source [file join $_root config project_config.tcl]
source [file join $_root config technology.tcl]
source [file join $_root config libraries.tcl]
source [file join $_root config flow_options.tcl]
source [file join $_root config physical_constraints.tcl]
source [file join $_root config rtl_files.tcl]
source [file join $_common_dir common_procs.tcl]
foreach d [list $WORK_DIR $LOG_DIR $REPORT_DIR $RESULT_DIR $CHECKPOINT_DIR $DATABASE_DIR \
                $NETLIST_DIR $SPEF_DIR $SDF_DIR $GDS_DIR $SAIF_DIR $EXTRACTED_DIR $FINAL_DIR $RUNS_DIR] {
    ensure_dir $d
}
