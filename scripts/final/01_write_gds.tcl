# =============================================================================
# Stage       : GDSII stream-out
# Tool        : Synopsys IC Compiler II
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "GDSII STREAM-OUT"
open_stage_block [get_active_physical_stage]
require_nonempty $GDS_LAYER_MAP GDS_LAYER_MAP
require_file $GDS_LAYER_MAP "GDS layer map"
set gds [file join $GDS_DIR "${PROJECT_NAME}.gds"]
if {![command_exists write_gds]} { fatal_error "write_gds is unavailable in this ICC2 release." }
write_gds -layer_map $GDS_LAYER_MAP $gds
require_file $gds "generated GDSII"
write_status gds GENERATED "GDS file generated. Foundry DRC/LVS status is independent and must not be inferred from stream-out."
write_checkpoint_marker [file join $CHECKPOINT_DIR final] gds GENERATED
stage_complete "GDSII STREAM-OUT"
exit 0
