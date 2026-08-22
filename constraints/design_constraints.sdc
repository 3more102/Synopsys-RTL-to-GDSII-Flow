# Design-rule constraints. Values are project policy and should be reviewed against the library.
if {![info exists MAX_TRANSITION]} { set MAX_TRANSITION 0.50 }
if {![info exists MAX_FANOUT]} { set MAX_FANOUT 16 }
if {![info exists MAX_CAPACITANCE]} { set MAX_CAPACITANCE 0.50 }
set_max_transition $MAX_TRANSITION [current_design]
set_max_fanout $MAX_FANOUT [current_design]
set_max_capacitance $MAX_CAPACITANCE [current_design]
