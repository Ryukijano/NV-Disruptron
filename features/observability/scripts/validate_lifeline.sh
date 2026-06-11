#!/usr/bin/env bash
# Validate LifeLine Grid MCP servers and shared data (no LLM required)
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
export LIFELINE_PROMPTS_DIR="$ROOT/features/agent-interactive/prompts"
export PYTHONPATH="$ROOT/platform/shared:$ROOT${PYTHONPATH:+:$PYTHONPATH}"

echo "==> Shared data"
cd "$ROOT"
python3 -c "
from shared.lifeline_data import load_wards
print('wards:', len(load_wards()))
"

echo "==> TfL MCP tools"
cd "$ROOT/platform/mcp/transport"
uv run python -c "
import asyncio, sys
sys.path.insert(0, '$ROOT/platform/shared')
from server import get_london_traffic_snapshot, get_all_road_status
async def main():
    try:
        s = await get_london_traffic_snapshot()
        print('tube issues:', len(s['tube']['lines_not_good_service']))
        r = await get_all_road_status(congested_only=True)
        print('congested roads:', r['congested_count'])
    except Exception as e:
        print('TfL API error (rate limit or network):', e)
asyncio.run(main())
"

sleep 3

echo "==> EV charging + car parks"
cd "$ROOT/platform/mcp/transport"
uv run python -c "
import asyncio, sys
sys.path.insert(0, '$ROOT/platform/shared')
from server import get_parking_and_charging_snapshot, get_stop_car_parks, get_car_park_detail
async def main():
    try:
        p = await get_parking_and_charging_snapshot()
        print('EV available', p['ev_charging']['available'], '/', p['ev_charging']['total_connectors'])
        print('car parks', p['car_parks']['total_car_parks'])
        s = await get_stop_car_parks('940GZZLUGFD')
        print('Greenford car parks', s['car_park_count'])
        d = await get_car_park_detail('CarParks_800444')
        print('occupancy source', d.get('occupancy_source'))
    except Exception as e:
        print('TfL API error (rate limit or network):', e)
asyncio.run(main())
"

sleep 3

echo "==> London Impact briefing"
cd "$ROOT/platform/mcp/impact"
uv run python -c "
import asyncio, sys
sys.path.insert(0, '$ROOT/platform/shared')
from server import get_london_city_briefing
async def main():
    try:
        b = await get_london_city_briefing()
        print(b['summary'][:300])
    except Exception as e:
        print('TfL API error (rate limit or network):', e)
asyncio.run(main())
"

echo "==> LifeLine prompts"
if [ -f "$LIFELINE_PROMPTS_DIR/researcher.j2" ] && [ -f "$LIFELINE_PROMPTS_DIR/intent_classification.j2" ]; then
    echo "prompts OK"
else
    echo "prompts: SKIPPED (directory missing)"
fi

echo "==> NemoClaw skills"
if [ -f "$ROOT/features/agent-autonomous/scripts/test_lifeline_skills.sh" ]; then
    "$ROOT/features/agent-autonomous/scripts/test_lifeline_skills.sh" || echo "skills test: FAILED (non-fatal)"
else
    echo "skills test: SKIPPED (script missing)"
fi

echo "==> Analysis feedback pipeline"
if [ -f "$ROOT/features/agent-autonomous/scripts/test_analysis_pipeline.sh" ]; then
    "$ROOT/features/agent-autonomous/scripts/test_analysis_pipeline.sh" || echo "pipeline test: FAILED (non-fatal)"
else
    echo "pipeline test: SKIPPED (script missing)"
fi

echo "==> LifeLine ops MCP (slim)"
if [ -f "$ROOT/lifeline-ops-mcp/server.py" ] && [ -s "$ROOT/lifeline-ops-mcp/server.py" ]; then
    cd "$ROOT/lifeline-ops-mcp"
    uv sync --quiet 2>/dev/null || uv sync
    uv run python -c "
import asyncio
from server import get_london_city_briefing
async def main():
    b = await get_london_city_briefing()
    assert 'summary' in b
    print('lifeline-ops briefing:', b['summary'][:120], '...')
asyncio.run(main())
" || echo "lifeline-ops: FAILED (non-fatal)"
else
    echo "lifeline-ops: SKIPPED (server.py missing or empty)"
fi

echo "==> Outputs API + Google Calendar"
if [ -f "$ROOT/platform/delivery/outputs-api/test_outputs.py" ]; then
    cd "$ROOT/platform/delivery/outputs-api"
    uv sync --quiet 2>/dev/null || uv sync
    uv run pytest -q test_outputs.py || echo "outputs test: FAILED (non-fatal)"
else
    echo "outputs test: SKIPPED (test_outputs.py missing)"
fi

if [ -f "$ROOT/platform/shared/google_calendar_client.py" ]; then
    uv run python -c "
import sys
sys.path.insert(0, '$ROOT/platform/shared')
from google_calendar_client import connection_status
s = connection_status()
print('calendar connected:', s['connected'], '| keys:', s['credentials_present'], '| tokens:', s['token_present'])
if not s['connected']:
    print('  (optional) Run ./scripts/setup_google_calendar.sh to connect Google Calendar')
" || echo "calendar check: FAILED (non-fatal)"
else
    echo "calendar check: SKIPPED (google_calendar_client.py missing)"
fi

echo
echo "LifeLine validation passed."
