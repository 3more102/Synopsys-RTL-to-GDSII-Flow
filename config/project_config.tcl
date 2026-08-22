# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : project_config.tcl
# Description : Project-specific configuration shared by all Synopsys stages.
# =============================================================================
proc cfg_env {name default} {
    if {[info exists ::env($name)] && $::env($name) ne ""} { return $::env($name) }
    return $default
}
set CONFIG_DIR [file normalize [file dirname [info script]]]
set PROJECT_ROOT [file normalize [cfg_env ASIC_PROJECT_ROOT [file join $CONFIG_DIR ..]]]
set PROJECT_NAME [cfg_env PROJECT_NAME MIPS_16]
set TOP_MODULE   [cfg_env TOP_MODULE mips_16]
set TECHNOLOGY   [cfg_env TECHNOLOGY SAED90nm]
set PROCESS_NODE [cfg_env PROCESS_NODE 90nm]
set FLOW_TYPE    "RTL-to-GDSII"

set RTL_DIR        [file join $PROJECT_ROOT rtl]
set CONSTRAINT_DIR [file join $PROJECT_ROOT constraints]
set POWER_INTENT_DIR [file join $PROJECT_ROOT power_intent]
set TECH_DIR       [file normalize [cfg_env TECH_DIR [file join $PROJECT_ROOT tech]]]
set LIB_DIR        [file normalize [cfg_env LIB_DIR  [file join $PROJECT_ROOT lib]]]
set WORK_DIR       [file join $PROJECT_ROOT work]
set LOG_DIR        [file join $PROJECT_ROOT logs]
set REPORT_DIR     [file join $PROJECT_ROOT reports]
set RESULT_DIR     [file join $PROJECT_ROOT results]
set CHECKPOINT_DIR [file join $PROJECT_ROOT checkpoints]
set DATABASE_DIR   [file join $PROJECT_ROOT database]
set NETLIST_DIR    [file join $PROJECT_ROOT netlist]
set SPEF_DIR       [file join $PROJECT_ROOT spef]
set SDF_DIR        [file join $PROJECT_ROOT sdf]
set GDS_DIR        [file join $PROJECT_ROOT gds]
set SAIF_DIR       [file join $PROJECT_ROOT saif]
set EXTRACTED_DIR  [file join $PROJECT_ROOT extracted]
set FINAL_DIR      [file join $PROJECT_ROOT final_delivery]
set RUNS_DIR       [file join $PROJECT_ROOT runs]

# Logical design constraints. Values are project assumptions, not PDK data.
set CLOCK_NAME   [cfg_env CLOCK_NAME clk]
set CLOCK_PORT   [cfg_env CLOCK_PORT clk]
set CLOCK_PERIOD [cfg_env CLOCK_PERIOD 10.0]
set CLOCK_UNCERTAINTY_SETUP [cfg_env CLOCK_UNCERTAINTY_SETUP 0.10]
set CLOCK_UNCERTAINTY_HOLD  [cfg_env CLOCK_UNCERTAINTY_HOLD 0.05]
set CLOCK_TRANSITION        [cfg_env CLOCK_TRANSITION 0.10]
set INPUT_DELAY             [cfg_env INPUT_DELAY 1.0]
set OUTPUT_DELAY            [cfg_env OUTPUT_DELAY 1.0]
set OUTPUT_LOAD             [cfg_env OUTPUT_LOAD 0.05]
set INPUT_DRIVING_CELL      [cfg_env INPUT_DRIVING_CELL ""]
set INPUT_TRANSITION        [cfg_env INPUT_TRANSITION 0.10]
set ASYNC_CONTROL_PORTS     [cfg_env ASYNC_CONTROL_PORTS ""]
set MAX_TRANSITION          [cfg_env MAX_TRANSITION 0.50]
set MAX_FANOUT              [cfg_env MAX_FANOUT 16]
set MAX_CAPACITANCE         [cfg_env MAX_CAPACITANCE 0.50]

# Floorplan methodology controls. These are intentionally configurable.
set CORE_UTILIZATION [cfg_env CORE_UTILIZATION 0.65]
set CORE_ASPECT_RATIO [cfg_env CORE_ASPECT_RATIO 1.0]
set CORE_OFFSET [cfg_env CORE_OFFSET 10]
set FLOORPLAN_USE_EXPLICIT_DIE [cfg_env FLOORPLAN_USE_EXPLICIT_DIE 0]
set DIE_BOUNDARY [cfg_env DIE_BOUNDARY ""]
set MACRO_HALO [cfg_env MACRO_HALO 5]
set MACRO_CHANNEL [cfg_env MACRO_CHANNEL 10]

# Acceptance targets. A stage is not declared closed unless evidence meets them.
set SETUP_WNS_TARGET 0.0
set SETUP_TNS_TARGET 0.0
set HOLD_WNS_TARGET  0.0
set ROUTING_DRC_TARGET 0
set MAX_PATHS [cfg_env MAX_PATHS 100]

