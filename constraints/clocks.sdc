# Primary clock definition. All values can be overridden by the parent Tcl flow.
if {![info exists CLOCK_NAME]} { set CLOCK_NAME clk }
if {![info exists CLOCK_PORT]} { set CLOCK_PORT clk }
if {![info exists CLOCK_PERIOD]} { set CLOCK_PERIOD 10.0 }
if {![info exists CLOCK_UNCERTAINTY_SETUP]} { set CLOCK_UNCERTAINTY_SETUP 0.10 }
if {![info exists CLOCK_UNCERTAINTY_HOLD]} { set CLOCK_UNCERTAINTY_HOLD 0.05 }
if {![info exists CLOCK_TRANSITION]} { set CLOCK_TRANSITION 0.10 }
create_clock -name $CLOCK_NAME -period $CLOCK_PERIOD [get_ports $CLOCK_PORT]
set_clock_uncertainty -setup $CLOCK_UNCERTAINTY_SETUP [get_clocks $CLOCK_NAME]
set_clock_uncertainty -hold  $CLOCK_UNCERTAINTY_HOLD  [get_clocks $CLOCK_NAME]
set_clock_transition $CLOCK_TRANSITION [get_clocks $CLOCK_NAME]
