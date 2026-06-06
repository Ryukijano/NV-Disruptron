# NV-Disruptron — shared environment (source only).

if [[ -z "${DISRUPTRON_ROOT:-}" ]]; then
  _src="${BASH_SOURCE[1]:-${BASH_SOURCE[0]}}"
  _dir="$(cd "$(dirname "$_src")" && pwd)"
  _candidate="$_dir"
  while [[ "$_candidate" != "/" ]]; do
    if [[ -f "$_candidate/data/london_wards_imd.csv" ]]; then
      DISRUPTRON_ROOT="$_candidate"
      break
    fi
    _candidate="$(dirname "$_candidate")"
  done
  : "${DISRUPTRON_ROOT:?Could not find NV-Disruptron repo root}"
fi

export DISRUPTRON_ROOT
export ROOT="$DISRUPTRON_ROOT"

export VLLM_SERVED_MODEL="${VLLM_SERVED_MODEL:-nemotron-3-nano-omni}"
export DISRUPTRON_REASONING="${DISRUPTRON_REASONING:-${NEMOCLAW_REASONING:-1}}"
export VLLM_BASE_URL="${VLLM_BASE_URL:-http://127.0.0.1:8000/v1}"
export DISRUPTRON_WORKSPACE="${DISRUPTRON_WORKSPACE:-$DISRUPTRON_ROOT/features/agent/workspace}"
export DISRUPTRON_HEARTBEAT_EVERY="${DISRUPTRON_HEARTBEAT_EVERY:-10m}"
export DISRUPTRON_SLIM_MCP="${DISRUPTRON_SLIM_MCP:-true}"
export AIQ_ROOT="${AIQ_ROOT:-/home/nvidia/aiq}"
export AIQ_SERVER_PORT="${AIQ_SERVER_PORT:-8001}"
export AIQ_SERVER_URL="${AIQ_SERVER_URL:-http://127.0.0.1:${AIQ_SERVER_PORT}}"
export DISRUPTRON_API_CONFIG="${DISRUPTRON_API_CONFIG:-$DISRUPTRON_ROOT/configs/config_disruptron_api.yml}"

# Optional repo secrets / overrides (gitignored)
if [[ -f "$DISRUPTRON_ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  set -a && source "$DISRUPTRON_ROOT/.env" && set +a
fi

export DISRUPTRON_GOOGLE_CALENDAR="${DISRUPTRON_GOOGLE_CALENDAR:-1}"
export GOOGLE_CALENDAR_MCP_DIR="${GOOGLE_CALENDAR_MCP_DIR:-$HOME/google-calendar-mcp}"
export GOOGLE_CALENDAR_MCP_PORT="${GOOGLE_CALENDAR_MCP_PORT:-3000}"
export VLLM_IMAGE="${VLLM_IMAGE:-vllm/vllm-openai:v0.20.0-aarch64-cu130-ubuntu2404}"
export VLLM_MEDIA_DIR="${VLLM_MEDIA_DIR:-/tmp/disruptron-media}"
