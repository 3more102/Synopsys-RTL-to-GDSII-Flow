# External interface timing assumptions.
if {![info exists INPUT_DELAY]} { set INPUT_DELAY 1.0 }
if {![info exists OUTPUT_DELAY]} { set OUTPUT_DELAY 1.0 }
if {![info exists OUTPUT_LOAD]} { set OUTPUT_LOAD 0.05 }
set _data_inputs [remove_from_collection [all_inputs] [get_ports -quiet $CLOCK_PORT]]
# Optional asynchronous control ports (for example an architecturally asynchronous reset)
# can be excluded from ordinary synchronous I/O-delay assumptions without declaring a false path here.
if {[info exists ASYNC_CONTROL_PORTS] && $ASYNC_CONTROL_PORTS ne ""} {
    set _async_ports [get_ports -quiet $ASYNC_CONTROL_PORTS]
    if {[sizeof_collection $_async_ports] > 0} { set _data_inputs [remove_from_collection $_data_inputs $_async_ports] }
}
if {[sizeof_collection $_data_inputs] > 0} { set_input_delay $INPUT_DELAY -clock $CLOCK_NAME $_data_inputs }
if {[sizeof_collection [all_outputs]] > 0} {
    set_output_delay $OUTPUT_DELAY -clock $CLOCK_NAME [all_outputs]
    set_load $OUTPUT_LOAD [all_outputs]
}
# A driving cell is technology-specific. Apply only when explicitly configured.
if {[info exists INPUT_DRIVING_CELL] && $INPUT_DRIVING_CELL ne "" && [sizeof_collection $_data_inputs] > 0} {
    set_driving_cell -lib_cell $INPUT_DRIVING_CELL $_data_inputs
} elseif {[info exists INPUT_TRANSITION] && [sizeof_collection $_data_inputs] > 0} {
    # A generic input transition is the fallback when no real library driving cell is configured.
    set_input_transition $INPUT_TRANSITION $_data_inputs
}
