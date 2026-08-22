# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 01_formality_setup.tcl
# Tool        : Synopsys Formality
# Description : Automation component for scripts/formal/01_formality_setup.tcl.
# =============================================================================
source [file join [file dirname [info script]] .. common load_config.tcl]
set SYN_DIR [file join $RESULT_DIR synthesis]
set SYN_NETLIST [file join $SYN_DIR "${PROJECT_NAME}_syn.v"]
set SVF_FILE [file join $SYN_DIR "${PROJECT_NAME}.svf"]
require_file $TARGET_LIBRARY "Formality technology library"
require_file $SYN_NETLIST "synthesized implementation netlist"
validate_file_list $RTL_FILES RTL
