# =============================================================================
# Project     : MIPS_16 ASIC Flow
# File        : physical_constraints.tcl
# Description : Explicit project geometry constraints. Edit only with real floorplan data.
# =============================================================================
# Macro entries: {instance_name x y orientation}. Coordinates are design units used by ICC2.
# Example (comment only):
# set MACRO_PLACEMENTS [list [list u_sram 100 200 N]]
set MACRO_PLACEMENTS [list]
set MACRO_FIX_PLACEMENT [cfg_env MACRO_FIX_PLACEMENT 1]

# Placement blockage entries: {name type boundary blocked_percentage}
# boundary can be {llx lly urx ury}; blocked_percentage is required only for type=partial.
set PLACEMENT_BLOCKAGES [list]

# Routing blockage entries: {name layer_list boundary}. Layer names must be real PDK layers.
set ROUTING_BLOCKAGES [list]

# Pin planning. A reviewed pin constraint file takes precedence over unconstrained automatic pin placement.
set AUTO_PLACE_PINS [cfg_env AUTO_PLACE_PINS 1]
set PIN_CONSTRAINT_FILE [cfg_env PIN_CONSTRAINT_FILE ""]
