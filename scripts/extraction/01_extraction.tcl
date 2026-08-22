# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : 01_extraction.tcl
# Stage       : Parasitic extraction / handoff
# Tool        : Synopsys IC Compiler II; optional StarRC
# Description : Writes SPEF from the final routed block and optional SBPF where supported.
# =============================================================================
source [file join [file dirname [info script]] .. floorplan icc2_common.tcl]
stage_banner "PARASITIC EXTRACTION"
open_stage_block [get_active_physical_stage]
set spef [file join $SPEF_DIR "${PROJECT_NAME}_postroute.spef"]
if {[command_exists write_parasitics]} {
    if {[catch {write_parasitics -format SPEF -output $spef} err]} {
        if {$ENABLE_STARRC} {
            fatal_error "ICC2 SPEF write failed: $err. A StarRC external run is enabled; generate/run the configured StarRC command file."
        }
        fatal_error "ICC2 SPEF write failed: $err"
    }
} elseif {$ENABLE_STARRC} {
    fatal_error "write_parasitics is unavailable. Run scripts/extraction/run_starrc.sh with a PDK-qualified STARRC_CMD_FILE, then rerun signoff."
} else {
    fatal_error "No extraction engine available: enable/configure StarRC or use an ICC2 release/license supporting write_parasitics."
}
require_file $spef "generated SPEF"
file copy -force $spef [file join $EXTRACTED_DIR "${PROJECT_NAME}.spef"]
if {$ENABLE_SBPF} {
    set sbpf [file join $EXTRACTED_DIR "${PROJECT_NAME}_postroute.sbpf"]
    if {[catch {write_parasitics -format SBPF -output $sbpf} sbpf_err]} {
        flow_warning "Optional SBPF generation failed/unsupported: $sbpf_err"
        write_status sbpf UNKNOWN "SBPF requested but could not be generated in this release/license."
    } else {
        write_status sbpf GENERATED "Optional SBPF generated from routed block."
    }
}
if {$ENABLE_DSPF} {
    write_status dspf UNKNOWN "DSPF/SPF requested: use a PDK-qualified StarRC command file; ICC2 SPEF is not relabeled as DSPF."
    flow_warning "ENABLE_DSPF=1 requires external StarRC setup; no fake DSPF was produced."
}
write_status extraction PASS "SPEF generated from final routed block. Optional formats retain independent status."
write_checkpoint_marker [file join $CHECKPOINT_DIR extraction] extraction PASS
stage_complete "PARASITIC EXTRACTION"
exit 0
