#!/usr/bin/env bash
# Validate LifeLine Grid MCP servers and shared data (no LLM required)
set -euo pipefail

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
cd "$ROOT/tfl-mcp-server"
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
cd "$ROOT/tfl-mcp-server"
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
cd "$ROOT/london-impact-mcp"
uv run python -c "
import asyncio
from server import get_london_city_briefing
async def main():
    b = await get_london_city_briefing()
    print(b['summary'][:300])
asyncio.run(main())
"

echo "==> LifeLine prompts"
test -f "$LIFELINE_PROMPTS_DIR/researcher.j2"
test -f "$LIFELINE_PROMPTS_DIR/intent_classification.j2"
echo "prompts OK"

echo "==> NemoClaw skills"
"$ROOT/features/agent-autonomous/scripts/test_lifeline_skills.sh"

echo "==> Analysis feedback pipeline"
"$ROOT/features/agent-autonomous/scripts/test_analysis_pipeline.sh"

echo "==> LifeLine ops MCP (slim)"
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
"

echo "==> Outputs API + Google Calendar"
cd "$ROOT/outputs-api"
uv sync --quiet 2>/dev/null || uv sync
uv run pytest -q test_outputs.py
uv run python -c "
import sys
sys.path.insert(0, '$ROOT/platform/shared')
from google_calendar_client import connection_status
s = connection_status()
print('calendar connected:', s['connected'], '| keys:', s['credentials_present'], '| tokens:', s['token_present'])
if not s['connected']:
    print('  (optional) Run ./scripts/setup_google_calendar.sh to connect Google Calendar')
"

echo
echo "LifeLine validation passed."
