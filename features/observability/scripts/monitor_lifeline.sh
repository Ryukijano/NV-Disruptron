#!/usr/bin/env bash
# LifeLine Grid health monitor — vLLM, MCP data, TfL API, prompts, live snapshot
# Usage:
#   ./scripts/monitor_lifeline.sh           # one-shot dashboard
#   ./scripts/monitor_lifeline.sh --watch   # refresh every 30s
#   ./scripts/monitor_lifeline.sh --json    # write logs/lifeline_status.json
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
LOG_DIR="$ROOT/logs"
STATUS_FILE="$LOG_DIR/lifeline_status.json"
VLLM_URL="${VLLM_BASE_URL:-http://127.0.0.1:8000/v1}"
PORT="${PORT:-8000}"
WATCH=0
JSON=0
VERBOSE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --watch|-w) WATCH=1; shift ;;
    --json|-j) JSON=1; shift ;;
    --verbose|-v) VERBOSE=1; shift ;;
    -h|--help)
      echo "Usage: $0 [--watch] [--json] [--verbose]"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

mkdir -p "$LOG_DIR"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export LIFELINE_PROMPTS_DIR="${LIFELINE_PROMPTS_DIR:-$ROOT/lifeline/prompts}"

check_mark() { printf '%s' "$1"; }
status_icon() {
  case "$1" in
    ok) echo "✅" ;;
    warn) echo "⚠️ " ;;
    fail) echo "❌" ;;
    *) echo "·" ;;
  esac
}

run_checks() {
  local ts vllm_status vllm_model docker_status tfl_status pc_status
  local wards data_csv prompts_ok aiq_venv briefing_line
  ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  # vLLM
  if curl -fsS "${VLLM_URL}/models" >/dev/null 2>&1; then
    vllm_status=ok
    vllm_model="$(curl -fsS "${VLLM_URL}/models" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data'][0]['id'] if d.get('data') else 'unknown')" 2>/dev/null || echo unknown)"
  else
    vllm_status=fail
    vllm_model=""
  fi

  # Docker (optional — vLLM may run outside docker)
  if command -v docker >/dev/null 2>&1; then
    if docker ps --filter name=vllm-nemotron-omni --format '{{.Status}}' 2>/dev/null | grep -q .; then
      docker_status="$(docker ps --filter name=vllm-nemotron-omni --format '{{.Status}}')"
    else
      docker_status="not running"
    fi
  else
    docker_status="docker unavailable"
  fi

  # TfL API
  if curl -fsS "https://api.tfl.gov.uk/Line/Mode/tube/Status" >/dev/null 2>&1; then
    tfl_status=ok
  else
    tfl_status=fail
  fi

  # postcodes.io
  if curl -fsS "https://api.postcodes.io/postcodes/SW1A1AA" >/dev/null 2>&1; then
    pc_status=ok
  else
    pc_status=warn
  fi

  # Data
  if [[ -f "$ROOT/data/london_wards_imd.csv" ]]; then
    data_csv=ok
    wards="$(cd "$ROOT" && python3 -c "from shared.lifeline_data import load_wards; print(len(load_wards()))" 2>/dev/null || echo 0)"
  else
    data_csv=fail
    wards=0
  fi

  # Prompts
  if [[ -f "$LIFELINE_PROMPTS_DIR/researcher.j2" && -f "$LIFELINE_PROMPTS_DIR/intent_classification.j2" ]]; then
    prompts_ok=ok
  else
    prompts_ok=fail
  fi

  # AI-Q venv
  if [[ -d "${AIQ_ROOT:-/home/nvidia/aiq}/.venv" ]]; then
    aiq_venv=ok
  else
    aiq_venv=warn
  fi

  # Live briefing one-liner (best-effort)
  ev_line="$(cd "$ROOT/tfl-mcp-server" && uv run python -c "
import asyncio
from server import get_parking_and_charging_snapshot
async def main():
    p = await get_parking_and_charging_snapshot()
    ev = p['ev_charging']
    cp = p['car_parks']
    print(f\"EV {ev['available']}/{ev['total_connectors']} available | car parks {cp['total_car_parks']} sites | occupancy API {cp['live_occupancy_api_status']}\")
asyncio.run(main())
" 2>/dev/null || echo "EV check failed")"

  briefing_line="$(cd "$ROOT/london-impact-mcp" && uv run python -c "
import asyncio
from server import get_london_city_briefing
async def main():
    try:
        b = await get_london_city_briefing()
        print(b.get('summary','')[:220])
    except Exception as e:
        print(f'BRIEFING_ERROR: {e}')
asyncio.run(main())
" 2>/dev/null || echo "BRIEFING_ERROR: could not run")"

  if [[ "$JSON" -eq 1 ]]; then
    python3 - <<PY
import json
from pathlib import Path
doc = {
  "timestamp": "$ts",
  "vllm": {"status": "$vllm_status", "url": "$VLLM_URL", "model": "$vllm_model"},
  "docker": "$docker_status",
  "tfl_api": "$tfl_status",
  "postcodes_io": "$pc_status",
  "data": {"status": "$data_csv", "ward_count": int("$wards")},
  "prompts": "$prompts_ok",
  "aiq_venv": "$aiq_venv",
  "ev_charging_preview": """${ev_line//\"/\\\"}""",
  "briefing_preview": """${briefing_line//\"/\\\"}""",
}
Path("$STATUS_FILE").write_text(json.dumps(doc, indent=2))
print("$STATUS_FILE")
PY
    return
  fi

  echo "══════════════════════════════════════════════════════════════"
  echo "  LifeLine Grid Monitor — $ts"
  echo "══════════════════════════════════════════════════════════════"
  echo ""
  echo "$(status_icon "$vllm_status") vLLM          ${VLLM_URL}  model=${vllm_model:-n/a}"
  echo "   Docker         ${docker_status}"
  echo "$(status_icon "$tfl_status") TfL API        https://api.tfl.gov.uk"
  echo "$(status_icon "$pc_status") postcodes.io   ward geocoding"
  echo "$(status_icon "$data_csv") Ward data      ${wards} wards (data/london_wards_imd.csv)"
  echo "$(status_icon "$prompts_ok") LifeLine prompts  ${LIFELINE_PROMPTS_DIR}"
  echo "$(status_icon "$aiq_venv") AI-Q venv      ${AIQ_ROOT:-/home/nvidia/aiq}/.venv"
  echo ""
  echo "── EV & car parks ──"
  echo "$ev_line"
  echo ""
  echo "── Live London snapshot ──"
  echo "$briefing_line"
  echo ""

  if [[ "$VERBOSE" -eq 1 ]]; then
    echo "── Recent vLLM log (last 5 lines) ──"
    tail -5 "$LOG_DIR/vllm-server.log" 2>/dev/null || echo "(no log)"
    echo ""
    if [[ -f "$ROOT/checkpoints.db" ]]; then
      echo "── Checkpoint DB ──"
      ls -lh "$ROOT/checkpoints.db"
    fi
  fi

  # Exit non-zero if critical deps down
  [[ "$vllm_status" == ok && "$tfl_status" == ok && "$data_csv" == ok && "$prompts_ok" == ok ]]
}

if [[ "$WATCH" -eq 1 ]]; then
  while true; do
    clear || true
    run_checks || true
    echo "Refreshing in 30s… (Ctrl+C to stop)"
    sleep 30
  done
else
  run_checks
fi
