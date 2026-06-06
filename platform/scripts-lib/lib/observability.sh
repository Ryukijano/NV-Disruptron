# Health monitor + smoke validation (no LLM required).

_disruptron_status_icon() {
  case "$1" in
    ok) echo "✅" ;;
    warn) echo "⚠️ " ;;
    fail) echo "❌" ;;
    *) echo "·" ;;
  esac
}

disruptron_cmd_monitor() {
  local log_dir="$DISRUPTRON_ROOT/logs"
  local status_file="$log_dir/disruptron_status.json"
  local vllm_url="${VLLM_BASE_URL:-http://127.0.0.1:8000/v1}"
  local workspace="${DISRUPTRON_WORKSPACE:-$DISRUPTRON_ROOT/features/agent/workspace}"
  local watch=0 json=0 verbose=0

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --watch|-w) watch=1; shift ;;
      --json|-j) json=1; shift ;;
      --verbose|-v) verbose=1; shift ;;
      -h|--help)
        cat <<EOF
Usage: disruptron monitor [--watch] [--json] [--verbose]
EOF
        return 0
        ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  mkdir -p "$log_dir"
  export PYTHONPATH="$DISRUPTRON_ROOT/platform/shared:$DISRUPTRON_ROOT${PYTHONPATH:+:$PYTHONPATH}"

  _disruptron_monitor_once() {
    local ts vllm_status vllm_model docker_status tfl_status pc_status
    local wards data_csv workspace_ok gateway_status aiq_api briefing_line ev_line
    ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

    if curl -fsS "${vllm_url}/models" >/dev/null 2>&1; then
      vllm_status=ok
      vllm_model="$(curl -fsS "${vllm_url}/models" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data'][0]['id'] if d.get('data') else 'unknown')" 2>/dev/null || echo unknown)"
    else
      vllm_status=fail
      vllm_model=""
    fi

    if command -v docker >/dev/null 2>&1; then
      if docker ps --filter name=vllm-nemotron-omni --format '{{.Status}}' 2>/dev/null | grep -q .; then
        docker_status="$(docker ps --filter name=vllm-nemotron-omni --format '{{.Status}}')"
      else
        docker_status="not running"
      fi
    else
      docker_status="docker unavailable"
    fi

    if curl -fsS "https://api.tfl.gov.uk/Line/Mode/tube/Status" >/dev/null 2>&1; then
      tfl_status=ok
    else
      tfl_status=fail
    fi

    if curl -fsS "https://api.postcodes.io/postcodes/SW1A1AA" >/dev/null 2>&1; then
      pc_status=ok
    else
      pc_status=warn
    fi

    if [[ -f "$DISRUPTRON_ROOT/data/london_wards_imd.csv" ]]; then
      data_csv=ok
      wards="$(cd "$DISRUPTRON_ROOT" && python3 -c "from shared.disruptron_data import load_wards; print(len(load_wards()))" 2>/dev/null || echo 0)"
    else
      data_csv=fail
      wards=0
    fi

    if curl -fsS "${AIQ_SERVER_URL:-http://127.0.0.1:8001}/health" >/dev/null 2>&1; then
      aiq_api=ok
    else
      aiq_api=warn
    fi

    if [[ -f "$workspace/AGENTS.md" && -f "$workspace/HEARTBEAT.md" ]]; then
      workspace_ok=ok
    else
      workspace_ok=fail
    fi

    if curl -fsS "http://127.0.0.1:18789/health" >/dev/null 2>&1; then
      gateway_status=ok
    else
      gateway_status=warn
    fi

    ev_line="$(cd "$DISRUPTRON_ROOT/platform/mcp/transport" && uv run python -c "
import asyncio
from server import get_parking_and_charging_snapshot
async def main():
    p = await get_parking_and_charging_snapshot()
    ev = p['ev_charging']
    cp = p['car_parks']
    print(f\"EV {ev['available']}/{ev['total_connectors']} available | car parks {cp['total_car_parks']} sites\")
asyncio.run(main())
" 2>/dev/null || echo "EV check failed")"

    briefing_line="$(cd "$DISRUPTRON_ROOT/platform/mcp/impact" && uv run python -c "
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

    if [[ "$json" -eq 1 ]]; then
      python3 - <<PY
import json
from pathlib import Path
doc = {
  "timestamp": "$ts",
  "vllm": {"status": "$vllm_status", "url": "$vllm_url", "model": "$vllm_model"},
  "docker": "$docker_status",
  "tfl_api": "$tfl_status",
  "postcodes_io": "$pc_status",
  "data": {"status": "$data_csv", "ward_count": int("$wards")},
  "workspace": "$workspace_ok",
  "openclaw_gateway": "$gateway_status",
  "aiq_research_api": "$aiq_api",
  "ev_charging_preview": """${ev_line//\"/\\\"}""",
  "briefing_preview": """${briefing_line//\"/\\\"}""",
}
Path("$status_file").write_text(json.dumps(doc, indent=2))
print("$status_file")
PY
      return
    fi

    echo "══════════════════════════════════════════════════════════════"
    echo "  NV-Disruptron Monitor — $ts"
    echo "══════════════════════════════════════════════════════════════"
    echo ""
    echo "$(_disruptron_status_icon "$vllm_status") vLLM          ${vllm_url}  model=${vllm_model:-n/a}"
    echo "   Docker         ${docker_status}"
    echo "$(_disruptron_status_icon "$tfl_status") TfL API        https://api.tfl.gov.uk"
    echo "$(_disruptron_status_icon "$pc_status") postcodes.io   ward geocoding"
    echo "$(_disruptron_status_icon "$data_csv") Ward data      ${wards} wards"
    echo "$(_disruptron_status_icon "$workspace_ok") Agent workspace  ${workspace}"
    echo "$(_disruptron_status_icon "$gateway_status") OpenClaw gateway  http://127.0.0.1:18789/"
    echo "$(_disruptron_status_icon "$aiq_api") AI-Q research   ${AIQ_SERVER_URL:-http://127.0.0.1:8001}"
    echo ""
    echo "── EV & car parks ──"
    echo "$ev_line"
    echo ""
    echo "── Live London snapshot ──"
    echo "$briefing_line"
    echo ""

    if [[ "$verbose" -eq 1 ]]; then
      echo "── Recent vLLM log (last 5 lines) ──"
      tail -5 "$log_dir/vllm-server.log" 2>/dev/null || echo "(no log)"
      echo ""
    fi

    [[ "$vllm_status" == ok && "$tfl_status" == ok && "$data_csv" == ok && "$workspace_ok" == ok ]]
  }

  if [[ "$watch" -eq 1 ]]; then
    while true; do
      clear || true
      _disruptron_monitor_once || true
      echo "Refreshing in 30s… (Ctrl+C to stop)"
      sleep 30
    done
  else
    _disruptron_monitor_once
  fi
}

disruptron_cmd_validate() {
  local root="$DISRUPTRON_ROOT"
  local workspace="${DISRUPTRON_WORKSPACE:-$root/features/agent/workspace}"
  export PYTHONPATH="$root/platform/shared:$root${PYTHONPATH:+:$PYTHONPATH}"

  echo "==> Shared data"
  cd "$root"
  python3 -c "
from shared.disruptron_data import load_wards
print('wards:', len(load_wards()))
"

  echo "==> TfL MCP tools"
  cd "$root/platform/mcp/transport"
  uv run python -c "
import asyncio
from server import get_london_traffic_snapshot, get_all_road_status
async def main():
    s = await get_london_traffic_snapshot()
    print('tube issues:', len(s['tube']['lines_not_good_service']))
    r = await get_all_road_status(congested_only=True)
    print('congested roads:', r['congested_count'])
asyncio.run(main())
"

  echo "==> EV charging + car parks"
  cd "$root/platform/mcp/transport"
  uv run python -c "
import asyncio
from server import get_parking_and_charging_snapshot, get_stop_car_parks, get_car_park_detail
async def main():
    p = await get_parking_and_charging_snapshot()
    print('EV available', p['ev_charging']['available'], '/', p['ev_charging']['total_connectors'])
    print('car parks', p['car_parks']['total_car_parks'])
    s = await get_stop_car_parks('940GZZLUGFD')
    print('Greenford car parks', s['car_park_count'])
    d = await get_car_park_detail('CarParks_800444')
    print('occupancy source', d.get('occupancy_source'))
asyncio.run(main())
"

  echo "==> London Impact briefing"
  cd "$root/platform/mcp/impact"
  uv run python -c "
import asyncio
from server import get_london_city_briefing
async def main():
    b = await get_london_city_briefing()
    print(b['summary'][:300])
asyncio.run(main())
"

  echo "==> OpenClaw agent workspace"
  test -f "$workspace/AGENTS.md"
  test -f "$workspace/HEARTBEAT.md"
  test -f "$workspace/TOOLS.md"
  echo "workspace OK ($workspace)"

  echo "==> Skills"
  _disruptron_test_skills

  echo "==> Analysis feedback pipeline"
  _disruptron_test_analysis

  echo "==> Disruptron ops MCP (slim)"
  cd "$root/platform/mcp/ops"
  uv sync --quiet 2>/dev/null || uv sync
  uv run python -c "
import asyncio
from server import get_london_city_briefing
async def main():
    b = await get_london_city_briefing()
    assert 'summary' in b
    print('disruptron-ops briefing:', b['summary'][:120], '...')
asyncio.run(main())
"

  if [[ -d "$root/outputs-api" ]]; then
    echo "==> Outputs API + Google Calendar"
    cd "$root/outputs-api"
    uv sync --quiet 2>/dev/null || uv sync
    uv run pytest -q test_outputs.py
    uv run python -c "
import sys
sys.path.insert(0, '$root/platform/shared')
from google_calendar_client import connection_status
s = connection_status()
print('calendar connected:', s['connected'])
if not s['connected']:
    print('  (optional) See platform/delivery/docs/GOOGLE_CALENDAR.md')
"
  else
    echo "==> Outputs API (skipped — symlink missing)"
  fi

  echo
  echo "NV-Disruptron validation passed."
}
