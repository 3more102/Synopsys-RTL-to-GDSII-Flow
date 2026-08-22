#!/usr/bin/env tclsh
# =============================================================================
# License-free configuration sanity checks. This sources only Tcl configuration
# files; it does not launch or require a Synopsys application.
# =============================================================================
set root [file normalize [file join [file dirname [info script]] ../..]]
source [file join $root config project_config.tcl]
source [file join $root config flow_options.tcl]
source [file join $root config technology.tcl]

set errors 0
set warnings 0
proc cfg_error {msg} { incr ::errors; puts stderr "CONFIG_ERROR: $msg" }
proc cfg_warn  {msg} { incr ::warnings; puts "CONFIG_WARNING: $msg" }
proc require_number {name value} {
    if {![string is double -strict $value]} { cfg_error "$name must be numeric; got '$value'"; return 0 }
    return 1
}
proc require_bool {name value} {
    if {$value ni {0 1 true false yes no on off}} { cfg_error "$name must be boolean-like; got '$value'" }
}

if {[require_number CLOCK_PERIOD $CLOCK_PERIOD] && $CLOCK_PERIOD <= 0} { cfg_error "CLOCK_PERIOD must be > 0" }
foreach {name value} [list CLOCK_UNCERTAINTY_SETUP $CLOCK_UNCERTAINTY_SETUP CLOCK_UNCERTAINTY_HOLD $CLOCK_UNCERTAINTY_HOLD INPUT_DELAY $INPUT_DELAY OUTPUT_DELAY $OUTPUT_DELAY CORE_OFFSET $CORE_OFFSET] {
    if {[require_number $name $value] && $value < 0} { cfg_error "$name must be >= 0" }
}
if {[require_number CORE_UTILIZATION $CORE_UTILIZATION]} {
    if {$CORE_UTILIZATION <= 0 || $CORE_UTILIZATION >= 1} { cfg_error "CORE_UTILIZATION must be between 0 and 1" }
    if {$CORE_UTILIZATION > 0.80} { cfg_warn "CORE_UTILIZATION=$CORE_UTILIZATION is aggressive; verify routability for the actual design/PDK" }
}
if {[require_number CORE_ASPECT_RATIO $CORE_ASPECT_RATIO] && $CORE_ASPECT_RATIO <= 0} { cfg_error "CORE_ASPECT_RATIO must be > 0" }
if {![string is integer -strict $MAX_PATHS] || $MAX_PATHS < 1} { cfg_error "MAX_PATHS must be an integer >= 1" }
if {![string is integer -strict $ROUTE_TIMING_CLOSURE_ITERS] || $ROUTE_TIMING_CLOSURE_ITERS < 0 || $ROUTE_TIMING_CLOSURE_ITERS > 20} { cfg_error "ROUTE_TIMING_CLOSURE_ITERS must be an integer from 0 to 20" }

foreach name {ENABLE_UPF ENABLE_CLOCK_GATING ENABLE_DFT ENABLE_SI ENABLE_SAIF_POWER ENABLE_STARRC ENABLE_ICV ENABLE_PG_GEOMETRY ENABLE_TAP_ENDCAP ENABLE_SPARE_CELLS ENABLE_FILLERS ENABLE_DECAPS ENABLE_TIE_CELLS} {
    require_bool $name [set $name]
}

if {$FLOORPLAN_USE_EXPLICIT_DIE && $DIE_BOUNDARY eq ""} { cfg_error "FLOORPLAN_USE_EXPLICIT_DIE=1 requires DIE_BOUNDARY" }
if {$ENABLE_STARRC && ($STARRC_TECH_FILE eq "" || $STARRC_MAP_FILE eq "")} { cfg_error "ENABLE_STARRC=1 requires STARRC_TECH_FILE and STARRC_MAP_FILE" }
if {$ENABLE_TAP_ENDCAP && ([llength $TAP_CELLS] == 0 || [llength $ENDCAP_CELLS] == 0)} { cfg_error "ENABLE_TAP_ENDCAP=1 requires TAP_CELLS and ENDCAP_CELLS" }
if {$ENABLE_FILLERS && [llength $FILLER_CELLS] == 0} { cfg_error "ENABLE_FILLERS=1 requires FILLER_CELLS" }
if {$ENABLE_DECAPS && [llength $DECAP_CELLS] == 0} { cfg_error "ENABLE_DECAPS=1 requires DECAP_CELLS" }
if {$ENABLE_SPARE_CELLS && [llength $SPARE_CELLS] == 0} { cfg_error "ENABLE_SPARE_CELLS=1 requires SPARE_CELLS" }
if {$ENABLE_TIE_CELLS && ([llength $TIE_HIGH_CELLS] == 0 || [llength $TIE_LOW_CELLS] == 0)} { cfg_error "ENABLE_TIE_CELLS=1 requires TIE_HIGH_CELLS and TIE_LOW_CELLS" }
if {$ENABLE_PG_GEOMETRY} {
    foreach name {PG_RING_H_LAYER PG_RING_V_LAYER PG_MESH_H_LAYER PG_MESH_V_LAYER PG_STD_CELL_RAIL_LAYER} {
        if {[set $name] eq ""} { cfg_warn "$name is unset; physical PG construction will intentionally stop until real PDK layers are configured" }
    }
}

puts "CONFIG_VALIDATION errors=$errors warnings=$warnings"
if {$errors > 0} { exit 1 }
exit 0
