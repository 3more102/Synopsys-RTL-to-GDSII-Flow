#!/usr/bin/env bash
# Source this file:  source setup.sh
_ASIC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$_ASIC_ROOT/.env.local" ]]; then source "$_ASIC_ROOT/.env.local"; fi
export ASIC_PROJECT_ROOT="${ASIC_PROJECT_ROOT:-$_ASIC_ROOT}"
export DC_SHELL="${DC_SHELL:-dc_shell}"
export ICC2_SHELL="${ICC2_SHELL:-icc2_shell}"
export PT_SHELL="${PT_SHELL:-pt_shell}"
export FM_SHELL="${FM_SHELL:-fm_shell}"
export STARRC="${STARRC:-StarXtract}"
export ICV="${ICV:-icv}"
export PYTHON="${PYTHON:-python3}"
printf 'ASIC_PROJECT_ROOT=%s\n' "$ASIC_PROJECT_ROOT"
printf 'Tools: DC=%s ICC2=%s PT=%s FM=%s StarRC=%s ICV=%s\n' "$DC_SHELL" "$ICC2_SHELL" "$PT_SHELL" "$FM_SHELL" "$STARRC" "$ICV"
