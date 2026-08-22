# Gate-Level Simulation Hook

`run_vcs_gls.sh` compiles the final netlist with a user-supplied testbench and standard-cell simulation models. SDF annotation scope is design-specific, so the script validates the final SDF but does not invent a DUT hierarchy path. The testbench should call `$sdf_annotate` using `SDF_ANNOTATE_SCOPE`/the generated SDF path.
