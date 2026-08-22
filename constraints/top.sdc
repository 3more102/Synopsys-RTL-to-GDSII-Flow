# Top-level SDC composition.
set _sdc_dir [file dirname [info script]]
source [file join $_sdc_dir clocks.sdc]
source [file join $_sdc_dir io.sdc]
source [file join $_sdc_dir design_constraints.sdc]
source [file join $_sdc_dir timing_exceptions.sdc]
