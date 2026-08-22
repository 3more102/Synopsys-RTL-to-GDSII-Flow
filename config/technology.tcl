# =============================================================================
# Technology-specific configuration. Fill from the installed PDK/SAED kit.
# Unknown PDK values deliberately default to empty; scripts fail when required.
# =============================================================================
source [file join [file dirname [info script]] project_config.tcl]
proc tech_env {name default} {
    if {[info exists ::env($name)] && $::env($name) ne ""} { return $::env($name) }
    return $default
}
set STD_CELL_NDM       [tech_env STD_CELL_NDM ""]
set TECH_FILE          [tech_env TECH_FILE ""]
set TLU_PLUS_MAX       [tech_env TLU_PLUS_MAX ""]
set TLU_PLUS_MIN       [tech_env TLU_PLUS_MIN ""]
set TLU_PLUS_MAP       [tech_env TLU_PLUS_MAP ""]
set GDS_LAYER_MAP      [tech_env GDS_LAYER_MAP ""]
set STARRC_MAP_FILE    [tech_env STARRC_MAP_FILE ""]
set STARRC_TECH_FILE   [tech_env STARRC_TECH_FILE ""]
set SITE_NAME          [tech_env SITE_NAME ""]
set MIN_ROUTING_LAYER  [tech_env MIN_ROUTING_LAYER ""]
set MAX_ROUTING_LAYER  [tech_env MAX_ROUTING_LAYER ""]

# PG layer names MUST come from the technology kit, not from guesses.
set PG_RING_H_LAYER    [tech_env PG_RING_H_LAYER ""]
set PG_RING_V_LAYER    [tech_env PG_RING_V_LAYER ""]
set PG_MESH_H_LAYER    [tech_env PG_MESH_H_LAYER ""]
set PG_MESH_V_LAYER    [tech_env PG_MESH_V_LAYER ""]
set PG_RING_WIDTH      [tech_env PG_RING_WIDTH 5.0]
set PG_RING_SPACING    [tech_env PG_RING_SPACING 2.0]
set PG_RING_OFFSET     [tech_env PG_RING_OFFSET 3.0]
set PG_MESH_H_WIDTH    [tech_env PG_MESH_H_WIDTH 2.0]
set PG_MESH_V_WIDTH    [tech_env PG_MESH_V_WIDTH 2.0]
set PG_MESH_H_PITCH    [tech_env PG_MESH_H_PITCH 30.0]
set PG_MESH_V_PITCH    [tech_env PG_MESH_V_PITCH 30.0]

set VDD_NET [tech_env VDD_NET VDD]
set VSS_NET [tech_env VSS_NET VSS]
set VDD_PORT_PATTERN [tech_env VDD_PORT_PATTERN VDD]
set VSS_PORT_PATTERN [tech_env VSS_PORT_PATTERN VSS]

# Special-cell lists are intentionally empty until discovered in the installed library.
set FILLER_CELLS [list]
set DECAP_CELLS  [list]
set SPARE_CELLS  [list]
set TAP_CELLS    [list]
set ENDCAP_CELLS [list]
set CTS_CELLS    [list]
set HOLD_CELLS   [list]
set TIE_HIGH_CELLS [list]
set TIE_LOW_CELLS  [list]
set TAP_DISTANCE        [tech_env TAP_DISTANCE ""]
set SPARE_NUM_INSTANCES [tech_env SPARE_NUM_INSTANCES 0]
set VCD_STRIP_PATH      [tech_env VCD_STRIP_PATH ""]
set SAIF_STRIP_PATH     [tech_env SAIF_STRIP_PATH ""]

# Additional physical implementation configuration.
# Values remain empty until identified from the actual technology/library.
set PG_STD_CELL_RAIL_LAYER [tech_env PG_STD_CELL_RAIL_LAYER ""]
set PG_STD_CELL_RAIL_WIDTH [tech_env PG_STD_CELL_RAIL_WIDTH ""]
set CTS_MIN_ROUTING_LAYER  [tech_env CTS_MIN_ROUTING_LAYER ""]
set CTS_MAX_ROUTING_LAYER  [tech_env CTS_MAX_ROUTING_LAYER ""]
set CTS_TARGET_SKEW        [tech_env CTS_TARGET_SKEW ""]
set CTS_TARGET_LATENCY     [tech_env CTS_TARGET_LATENCY ""]
set CTS_NDR_MULTIPLIER     [tech_env CTS_NDR_MULTIPLIER ""]

# Allow special-cell references to be injected as Tcl lists through environment variables.
# Example: export FILLER_CELLS='lib/FILL1 lib/FILL2'
foreach _cell_var {FILLER_CELLS DECAP_CELLS SPARE_CELLS TAP_CELLS ENDCAP_CELLS CTS_CELLS HOLD_CELLS TIE_HIGH_CELLS TIE_LOW_CELLS} {
    if {[info exists ::env($_cell_var)] && $::env($_cell_var) ne ""} { set $_cell_var $::env($_cell_var) }
}

# Compatibility aliases used by documentation/legacy project variable naming.
set MAP_FILE $TLU_PLUS_MAP
set PG_STRAP_H_LAYER $PG_MESH_H_LAYER
set PG_STRAP_V_LAYER $PG_MESH_V_LAYER
