# Functional/test modes. Test mode stays disabled until DFT constraints exist.
set MODES [dict create \
    functional [dict create sdc [file join $CONSTRAINT_DIR top.sdc] enabled 1] \
    test       [dict create sdc "" enabled 0]]
