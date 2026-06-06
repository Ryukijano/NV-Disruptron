# LifeLine Grid — shared shell helpers
# Usage: source "$(dirname "$0")/../../platform/scripts-lib/common.sh"  (from features/*/scripts)

if [[ -z "${LIFELINE_ROOT:-}" ]]; then
  _src="${BASH_SOURCE[1]:-${BASH_SOURCE[0]}}"
  _dir="$(cd "$(dirname "$_src")" && pwd)"
  # Walk up to repo root (contains data/london_wards_imd.csv)
  _candidate="$_dir"
  while [[ "$_candidate" != "/" ]]; do
    if [[ -f "$_candidate/data/london_wards_imd.csv" ]]; then
      LIFELINE_ROOT="$_candidate"
      break
    fi
    _candidate="$(dirname "$_candidate")"
  done
  : "${LIFELINE_ROOT:?Could not find LifeLine repo root}"
fi
export LIFELINE_ROOT
ROOT="${LIFELINE_ROOT}"

export VLLM_SERVED_MODEL="${VLLM_SERVED_MODEL:-nemotron_3_nano_omni}"
export AIQ_ROOT="${AIQ_ROOT:-/home/nvidia/aiq}"
export LIFELINE_PROMPTS_DIR="${LIFELINE_PROMPTS_DIR:-$LIFELINE_ROOT/features/agent-interactive/prompts}"
export NEMOCLAW_WORKSPACE="${NEMOCLAW_WORKSPACE:-$LIFELINE_ROOT/features/agent-autonomous/workspace}"
