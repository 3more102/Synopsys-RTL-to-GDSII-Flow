# =============================================================================
# Stage       : Environment validation
# Tool        : Generic Synopsys Tcl shell (dc_shell recommended)
# =============================================================================
source [file join [file dirname [info script]] load_config.tcl]
stage_banner "ENVIRONMENT VALIDATION"
foreach d [list $PROJECT_ROOT $RTL_DIR $CONSTRAINT_DIR $WORK_DIR $LOG_DIR $REPORT_DIR] { require_dir $d }
validate_file_list $RTL_FILES RTL
require_file [file join $CONSTRAINT_DIR top.sdc] "top-level SDC"
require_file $TARGET_LIBRARY "target .db library"
if {[llength $NDM_REFERENCE_LIBRARIES] == 0} { fatal_error "No NDM reference library configured (STD_CELL_NDM)." }
foreach lib $NDM_REFERENCE_LIBRARIES { require_path $lib "NDM reference library" }
if {$TECH_FILE ne ""} { require_file $TECH_FILE "technology file" } else { flow_warning "TECH_FILE is empty; ICC2 create_lib may rely on technology embedded in the reference NDM." }
if {$TLU_PLUS_MAX ne ""} { require_file $TLU_PLUS_MAX "TLU+ max" } else { flow_warning "TLU_PLUS_MAX not configured; signoff RC setup remains incomplete." }
if {$TLU_PLUS_MIN ne ""} { require_file $TLU_PLUS_MIN "TLU+ min" } else { flow_warning "TLU_PLUS_MIN not configured; min-RC setup remains incomplete." }
if {$GDS_LAYER_MAP eq ""} { flow_warning "GDS_LAYER_MAP is not configured; stream-out will intentionally fail until provided." }
foreach _pgvar {PG_RING_H_LAYER PG_RING_V_LAYER PG_MESH_H_LAYER PG_MESH_V_LAYER PG_STD_CELL_RAIL_LAYER} {
    if {[set $_pgvar] eq ""} { flow_warning "$_pgvar is empty; make powerplan will intentionally stop until a real PDK layer is configured." }
}
if {$CORE_UTILIZATION <= 0.0 || $CORE_UTILIZATION >= 1.0} { fatal_error "CORE_UTILIZATION must be between 0 and 1 (exclusive): $CORE_UTILIZATION" }
if {$CORE_ASPECT_RATIO <= 0.0} { fatal_error "CORE_ASPECT_RATIO must be positive: $CORE_ASPECT_RATIO" }
if {$CLOCK_PERIOD <= 0.0} { fatal_error "CLOCK_PERIOD must be positive: $CLOCK_PERIOD" }
write_status environment PASS "Required RTL, SDC, logical library, and NDM inputs found. Optional/signoff technology values are reported separately as warnings."
write_checkpoint_marker [file join $CHECKPOINT_DIR environment] environment PASS
stage_complete "ENVIRONMENT VALIDATION"
exit 0
