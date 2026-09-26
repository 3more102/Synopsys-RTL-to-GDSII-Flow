#!/usr/bin/env python3
"""Targeted low-current continuation of the verified PTAT design sweep."""
import run_sky130_design_sweeps_ci as sweep

# Keep the same SKY130 devices and N=8 geometry; only move deeper into
# weak inversion and hold VDD at the lowest already-proven headroom point.
sweep.VDDS = (1.2,)
sweep.CURRENTS = (1e-9, 3e-9, 10e-9)

if __name__ == "__main__":
    raise SystemExit(sweep.main())
