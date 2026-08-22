# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 02_gui_screenshot_helper.tcl
# Stage       : Floorplan GUI capture
# Tool        : Synopsys IC Compiler II GUI
# Run         : icc2_shell -gui -f scripts/floorplan/02_gui_screenshot_helper.tcl
# Description : Fits the saved floorplan in a Layout window and writes a PNG when GUI commands are available.
# =============================================================================
source [file join [file dirname [info script]] icc2_common.tcl]
stage_banner "FLOORPLAN SCREENSHOT"
open_stage_block floorplan
set out [file join $PROJECT_ROOT screenshots "${PROJECT_NAME}_floorplan.png"]
ensure_dir [file dirname $out]
if {![info exists ::env(DISPLAY)] || $::env(DISPLAY) eq ""} {
    fatal_error "DISPLAY is not set. Run this target from an X11/desktop session or save the screenshot manually in ICC2 GUI."
}
foreach cmd {gui_start gui_get_current_window gui_create_window gui_zoom gui_write_window_image} {
    if {![command_exists $cmd]} { fatal_error "GUI command '$cmd' is unavailable in this ICC2 release/session." }
}
catch {gui_start} _gui_start_note
set win [gui_get_current_window -types Layout -mru]
if {$win eq ""} { set win [gui_create_window -type LayoutWindow] }
gui_zoom -window $win -fit
gui_write_window_image -window $win -format png -file $out
require_file $out "floorplan screenshot"
flow_info "Floorplan screenshot written: $out"
stage_complete "FLOORPLAN SCREENSHOT"
exit 0
