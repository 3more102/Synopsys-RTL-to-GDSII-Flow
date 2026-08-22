SHELL := /bin/bash
ROOT := $(CURDIR)
DC_SHELL ?= dc_shell
ICC2_SHELL ?= icc2_shell
PT_SHELL ?= pt_shell
FM_SHELL ?= fm_shell
PYTHON ?= python3
STARRC ?= StarXtract
ICV ?= icv
export DC_SHELL ICC2_SHELL PT_SHELL FM_SHELL PYTHON STARRC ICV
LOG := $(ROOT)/logs
TS = $(shell date +%Y%m%d_%H%M%S)
RTL_SRCS := $(wildcard rtl/*.v rtl/*.sv)
CONFIGS := $(wildcard config/*.tcl)
SDCS := $(wildcard constraints/*.sdc)
COMMON := $(wildcard scripts/common/*.tcl)

.PHONY: help static config-check test-parsers env lint synth formal presta init floorplan floorplan-screenshot powerplan place prects cts postcts route postroute closure outputs extract signoff power saif-power vcd-power physical-cells spares tie-cells fillers eco eco-analyze setup-eco hold-eco drc-eco pv drc lvs ir-em gds reports summary final verify release snapshot dse all check clean clean-results distclean

ENV_STAMP := checkpoints/environment/environment.status
LINT_STAMP := checkpoints/lint/lint.status
SYN_STAMP := checkpoints/synthesis/synthesis.status
FORMAL_STAMP := checkpoints/formal/formal.status
PRESTA_STAMP := checkpoints/presta/presta.status
INIT_STAMP := checkpoints/init/init.status
FP_STAMP := checkpoints/floorplan/floorplan.status
PHYS_ONLY_STAMP := reports/status/physical_only.status
PG_STAMP := checkpoints/powerplan/powerplan.status
PLACE_STAMP := checkpoints/placement/placement.status
SPARES_STAMP := reports/status/spares.status
TIE_STAMP := reports/status/tie_cells.status
PRECTS_STAMP := checkpoints/pre_cts/pre_cts.status
CTS_STAMP := checkpoints/post_cts/post_cts.status
POSTCTS_STAMP := checkpoints/post_cts_opt/post_cts_opt.status
ROUTE_STAMP := checkpoints/route/route.status
POSTROUTE_STAMP := checkpoints/post_route/post_route.status
CLOSURE_STAMP := checkpoints/final_route/final_route.status
FILLERS_STAMP := reports/status/fillers.status
OUTPUTS_STAMP := reports/status/final_outputs.status
EXTRACT_STAMP := checkpoints/extraction/extraction.status
SIGNOFF_STAMP := checkpoints/signoff/signoff.status
POWER_STAMP := reports/status/power.status
DRC_STAMP := reports/status/drc.status
GDS_STAMP := checkpoints/final/gds.status
LVS_STAMP := reports/status/lvs.status
SUMMARY_STAMP := reports/summary/qor_summary.json
FINAL_STAMP := final_delivery/MANIFEST.txt

help:
	@echo "Complete ASIC flow targets:"
	@echo "  env lint synth formal presta init floorplan floorplan-screenshot powerplan place prects cts postcts"
	@echo "  route postroute closure outputs extract signoff power eco drc gds lvs reports final verify release all"
	@echo "  static = license-free repository validation; config-check = Tcl config sanity; test-parsers = parser unit tests"
	@echo "  release = final + verify + snapshot"
	@echo "Stamps prevent expensive completed stages from rerunning when their inputs are unchanged."
	@echo "After changing physical technology/floorplan inputs, use 'make distclean' deliberately before rebuilding the ICC2 database."

static:
	@bash scripts/common/static_validate.sh

config-check:
	@tclsh scripts/common/validate_config.tcl

test-parsers:
	@PYTHONPATH="$(ROOT)/python" $(PYTHON) -m unittest discover -s tests -p "test_*.py" -v

env: $(ENV_STAMP)
$(ENV_STAMP): $(CONFIGS) $(SDCS) $(COMMON) $(RTL_SRCS)
	@mkdir -p $(LOG); bash scripts/common/check_tools.sh | tee $(LOG)/00_tools_$(TS).log
	@bash scripts/common/run_stage.sh environment $(DC_SHELL) scripts/common/check_environment.tcl $(LOG)/01_environment_$(TS).log
	@bash scripts/common/run_stage.sh manifest $(DC_SHELL) scripts/common/report_environment.tcl $(LOG)/02_manifest_$(TS).log
	@bash scripts/common/create_run_manifest.sh >/dev/null

lint: $(LINT_STAMP)
$(LINT_STAMP): $(ENV_STAMP) scripts/lint/generic_rtl_check.tcl $(RTL_SRCS)
	@bash scripts/common/run_stage.sh lint $(DC_SHELL) scripts/lint/generic_rtl_check.tcl $(LOG)/05_lint_$(TS).log

synth: $(SYN_STAMP)
$(SYN_STAMP): $(LINT_STAMP) scripts/synthesis/01_synthesis.tcl $(RTL_SRCS) $(SDCS) $(CONFIGS)
	@bash scripts/common/run_stage.sh synthesis $(DC_SHELL) scripts/synthesis/01_synthesis.tcl $(LOG)/10_synthesis_$(TS).log

formal: $(FORMAL_STAMP)
$(FORMAL_STAMP): $(SYN_STAMP) scripts/formal/01_formality_setup.tcl scripts/formal/02_rtl_vs_synth.tcl
	@bash scripts/common/run_stage.sh formality $(FM_SHELL) scripts/formal/02_rtl_vs_synth.tcl $(LOG)/20_formality_$(TS).log

presta: $(PRESTA_STAMP)
$(PRESTA_STAMP): $(SYN_STAMP) scripts/sta/01_prelayout_sta.tcl
	@bash scripts/common/run_stage.sh prelayout_sta $(PT_SHELL) scripts/sta/01_prelayout_sta.tcl $(LOG)/30_prelayout_sta_$(TS).log

init: $(INIT_STAMP)
$(INIT_STAMP): $(SYN_STAMP) scripts/floorplan/00_create_design_lib.tcl scripts/floorplan/icc2_common.tcl
	@bash scripts/common/run_stage.sh icc2_init $(ICC2_SHELL) scripts/floorplan/00_create_design_lib.tcl $(LOG)/35_icc2_init_$(TS).log

floorplan: $(FP_STAMP)
$(FP_STAMP): $(INIT_STAMP) scripts/floorplan/01_floorplan.tcl
	@bash scripts/common/run_stage.sh floorplan $(ICC2_SHELL) scripts/floorplan/01_floorplan.tcl $(LOG)/40_floorplan_$(TS).log

floorplan-screenshot: $(FP_STAMP)
	@EDA_TOOL_ARGS=-gui bash scripts/common/run_stage.sh floorplan_screenshot $(ICC2_SHELL) scripts/floorplan/02_gui_screenshot_helper.tcl $(LOG)/41_floorplan_screenshot_$(TS).log

physical-cells: $(PHYS_ONLY_STAMP)
$(PHYS_ONLY_STAMP): $(FP_STAMP) scripts/floorplan/03_physical_only_cells.tcl config/technology.tcl
	@bash scripts/common/run_stage.sh physical_only $(ICC2_SHELL) scripts/floorplan/03_physical_only_cells.tcl $(LOG)/45_physical_only_$(TS).log

powerplan: $(PG_STAMP)
$(PG_STAMP): $(PHYS_ONLY_STAMP) scripts/powerplan/01_powerplan.tcl config/technology.tcl
	@bash scripts/common/run_stage.sh powerplan $(ICC2_SHELL) scripts/powerplan/01_powerplan.tcl $(LOG)/50_powerplan_$(TS).log

place: $(PLACE_STAMP)
$(PLACE_STAMP): $(PG_STAMP) scripts/placement/01_place_opt.tcl
	@bash scripts/common/run_stage.sh placement $(ICC2_SHELL) scripts/placement/01_place_opt.tcl $(LOG)/60_placement_$(TS).log

spares: $(SPARES_STAMP)
$(SPARES_STAMP): $(PLACE_STAMP) scripts/placement/04_spare_cells.tcl config/technology.tcl
	@bash scripts/common/run_stage.sh spares $(ICC2_SHELL) scripts/placement/04_spare_cells.tcl $(LOG)/61_spares_$(TS).log

tie-cells: $(TIE_STAMP)
$(TIE_STAMP): $(SPARES_STAMP) scripts/placement/05_tie_cells.tcl config/technology.tcl
	@bash scripts/common/run_stage.sh tie_cells $(ICC2_SHELL) scripts/placement/05_tie_cells.tcl $(LOG)/62_tie_cells_$(TS).log

prects: $(PRECTS_STAMP)
$(PRECTS_STAMP): $(TIE_STAMP) scripts/placement/03_pre_cts_opt.tcl
	@bash scripts/common/run_stage.sh pre_cts $(ICC2_SHELL) scripts/placement/03_pre_cts_opt.tcl $(LOG)/65_prects_$(TS).log

cts: $(CTS_STAMP)
$(CTS_STAMP): $(PRECTS_STAMP) scripts/cts/01_cts_setup.tcl scripts/cts/02_clock_opt.tcl
	@bash scripts/common/run_stage.sh cts $(ICC2_SHELL) scripts/cts/02_clock_opt.tcl $(LOG)/70_cts_$(TS).log

postcts: $(POSTCTS_STAMP)
$(POSTCTS_STAMP): $(CTS_STAMP) scripts/cts/04_post_cts_opt.tcl
	@bash scripts/common/run_stage.sh post_cts $(ICC2_SHELL) scripts/cts/04_post_cts_opt.tcl $(LOG)/75_postcts_$(TS).log

route: $(ROUTE_STAMP)
$(ROUTE_STAMP): $(POSTCTS_STAMP) scripts/routing/01_route.tcl
	@bash scripts/common/run_stage.sh route $(ICC2_SHELL) scripts/routing/01_route.tcl $(LOG)/80_route_$(TS).log

postroute: $(POSTROUTE_STAMP)
$(POSTROUTE_STAMP): $(ROUTE_STAMP) scripts/routing/02_route_opt.tcl
	@bash scripts/common/run_stage.sh route_opt $(ICC2_SHELL) scripts/routing/02_route_opt.tcl $(LOG)/82_route_opt_$(TS).log

closure: $(CLOSURE_STAMP)
$(CLOSURE_STAMP): $(POSTROUTE_STAMP) scripts/routing/04_timing_closure.tcl
	@bash scripts/common/run_stage.sh closure $(ICC2_SHELL) scripts/routing/04_timing_closure.tcl $(LOG)/84_closure_$(TS).log

fillers: $(FILLERS_STAMP)
$(FILLERS_STAMP): $(CLOSURE_STAMP) scripts/final/02_insert_fillers.tcl config/technology.tcl
	@bash scripts/common/run_stage.sh fillers $(ICC2_SHELL) scripts/final/02_insert_fillers.tcl $(LOG)/85_fillers_$(TS).log

outputs: $(OUTPUTS_STAMP)
$(OUTPUTS_STAMP): $(FILLERS_STAMP) scripts/final/00_write_outputs.tcl
	@bash scripts/common/run_stage.sh outputs $(ICC2_SHELL) scripts/final/00_write_outputs.tcl $(LOG)/86_outputs_$(TS).log

extract: $(EXTRACT_STAMP)
$(EXTRACT_STAMP): $(OUTPUTS_STAMP) scripts/extraction/01_extraction.tcl
	@bash scripts/common/run_stage.sh extraction $(ICC2_SHELL) scripts/extraction/01_extraction.tcl $(LOG)/88_extract_$(TS).log

signoff: $(SIGNOFF_STAMP)
$(SIGNOFF_STAMP): $(EXTRACT_STAMP) scripts/signoff/01_postroute_sta.tcl
	@bash scripts/common/run_stage.sh signoff $(PT_SHELL) scripts/signoff/01_postroute_sta.tcl $(LOG)/90_signoff_$(TS).log

power: $(POWER_STAMP)
$(POWER_STAMP): $(SIGNOFF_STAMP) scripts/power/01_vectorless_power.tcl
	@bash scripts/common/run_stage.sh power $(PT_SHELL) scripts/power/01_vectorless_power.tcl $(LOG)/92_power_$(TS).log

saif-power: $(SIGNOFF_STAMP)
	@bash scripts/common/run_stage.sh saif_power $(PT_SHELL) scripts/power/02_saif_power.tcl $(LOG)/93_saif_power_$(TS).log
vcd-power: $(SIGNOFF_STAMP)
	@bash scripts/common/run_stage.sh vcd_power $(PT_SHELL) scripts/power/02_vcd_power.tcl $(LOG)/93_vcd_power_$(TS).log

eco-analyze: $(CLOSURE_STAMP)
	@bash scripts/common/run_stage.sh eco_analyze $(ICC2_SHELL) scripts/eco/01_analyze_violations.tcl $(LOG)/94_eco_analyze_$(TS).log
setup-eco: eco-analyze
	@bash scripts/common/run_stage.sh setup_eco $(ICC2_SHELL) scripts/eco/02_setup_eco.tcl $(LOG)/95_setup_eco_$(TS).log
hold-eco: setup-eco
	@bash scripts/common/run_stage.sh hold_eco $(ICC2_SHELL) scripts/eco/03_hold_eco.tcl $(LOG)/96_hold_eco_$(TS).log
eco: hold-eco
	@bash scripts/common/run_stage.sh eco_verify $(ICC2_SHELL) scripts/eco/06_verify_eco.tcl $(LOG)/97_eco_verify_$(TS).log
	@bash scripts/common/invalidate_after_eco.sh

drc: $(DRC_STAMP)
$(DRC_STAMP): $(POWER_STAMP) scripts/physical_verification/01_drc_setup.tcl
	@bash scripts/common/run_stage.sh drc_prep $(ICC2_SHELL) scripts/physical_verification/01_drc_setup.tcl $(LOG)/98_drc_prep_$(TS).log

ir-em: $(POWER_STAMP)
	@bash scripts/common/run_stage.sh ir_em_prep $(ICC2_SHELL) scripts/physical_verification/03_ir_em_prep.tcl $(LOG)/98_ir_em_$(TS).log

gds: $(GDS_STAMP)
$(GDS_STAMP): $(DRC_STAMP) scripts/final/01_write_gds.tcl
	@bash scripts/common/run_stage.sh gds $(ICC2_SHELL) scripts/final/01_write_gds.tcl $(LOG)/100_gds_$(TS).log

lvs: $(LVS_STAMP)
$(LVS_STAMP): $(GDS_STAMP) scripts/physical_verification/02_lvs_setup.tcl
	@bash scripts/common/run_stage.sh lvs_prep $(DC_SHELL) scripts/physical_verification/02_lvs_setup.tcl $(LOG)/101_lvs_prep_$(TS).log

pv: drc lvs
reports summary: $(SUMMARY_STAMP)
$(SUMMARY_STAMP): $(SIGNOFF_STAMP) python/generate_summary.py python/report_utils.py
	@$(PYTHON) python/evaluate_status.py
	@$(PYTHON) python/generate_summary.py

final: $(FINAL_STAMP)
$(FINAL_STAMP): $(LVS_STAMP) $(SUMMARY_STAMP) scripts/final/collect_deliverables.sh
	@bash scripts/final/collect_deliverables.sh

verify: $(FINAL_STAMP) config/stage_contracts.json python/verify_artifacts.py python/report_utils.py
	@$(PYTHON) python/verify_artifacts.py

release: final verify snapshot

snapshot:
	@bash scripts/common/create_run_snapshot.sh

dse:
	@bash scripts/dse/run_dse.sh

check: static env
all: formal presta release

clean:
	@bash clean.sh clean
clean-results:
	@bash clean.sh clean-results
distclean:
	@bash clean.sh distclean
