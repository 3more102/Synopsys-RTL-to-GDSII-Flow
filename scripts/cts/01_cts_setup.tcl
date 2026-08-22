# =============================================================================
# Stage       : CTS setup helper
# Tool        : Synopsys IC Compiler II
# Description : Applies configured clock-cell references, skew/latency, clock DRC and routing/NDR policy.
# =============================================================================
if {[llength $CTS_CELLS] == 0} {
    flow_warning "CTS_CELLS is empty; ICC2 will use library-legal clock cells per its current purposes. Configure explicit references if methodology requires them."
} else {
    foreach c $CTS_CELLS {
        if {[sizeof_collection [get_lib_cells -quiet $c]] == 0} { fatal_error "Configured CTS library cell not found: $c" }
    }
    if {[command_exists set_lib_cell_purpose]} { set_lib_cell_purpose -include cts [get_lib_cells $CTS_CELLS] }
}
if {$CTS_TARGET_SKEW ne ""} {
    set_clock_tree_options -clocks [all_clocks] -target_skew $CTS_TARGET_SKEW
}
if {$CTS_TARGET_LATENCY ne ""} {
    set_clock_tree_options -clocks [all_clocks] -target_latency $CTS_TARGET_LATENCY
}
if {[command_exists set_max_transition]} {
    catch {set_max_transition $CLOCK_TRANSITION -clock_path [all_clocks]} _cts_tr_err
    if {[info exists _cts_tr_err] && $_cts_tr_err ne ""} { flow_warning "Clock-path max-transition setup note: $_cts_tr_err" }
}
if {$CTS_MIN_ROUTING_LAYER ne "" || $CTS_MAX_ROUTING_LAYER ne ""} {
    require_nonempty $CTS_MIN_ROUTING_LAYER CTS_MIN_ROUTING_LAYER
    require_nonempty $CTS_MAX_ROUTING_LAYER CTS_MAX_ROUTING_LAYER
    if {$CTS_NDR_MULTIPLIER ne ""} {
        if {![command_exists create_routing_rule]} { fatal_error "CTS NDR requested but create_routing_rule is unavailable." }
        create_routing_rule CTS_NDR -default_reference_rule \
            -multiplier_width $CTS_NDR_MULTIPLIER -multiplier_spacing $CTS_NDR_MULTIPLIER
        set_clock_routing_rules -clocks [all_clocks] -net_type all -rules CTS_NDR \
            -min_routing_layer $CTS_MIN_ROUTING_LAYER -max_routing_layer $CTS_MAX_ROUTING_LAYER
    } else {
        set_clock_routing_rules -clocks [all_clocks] -net_type all \
            -min_routing_layer $CTS_MIN_ROUTING_LAYER -max_routing_layer $CTS_MAX_ROUTING_LAYER
    }
}
