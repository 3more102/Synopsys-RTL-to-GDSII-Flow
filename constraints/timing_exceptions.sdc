# Timing exceptions intentionally empty by default.
# Add a false path or multicycle path only after architectural justification and review.
# Example templates (commented out):
# set_false_path -from [get_clocks A] -to [get_clocks B]
# set_multicycle_path 2 -setup -from <start> -to <end>
# set_multicycle_path 1 -hold  -from <start> -to <end>
