#!/usr/bin/env bash
# Smoke test TfL EV charging + car park MCP tools (no LLM)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

echo "==> Parking & charging snapshot"
cd "$ROOT/tfl-mcp-server"
uv run python -c "
import asyncio, json
from server import (
    get_parking_and_charging_snapshot,
    get_ev_charge_connectors,
    list_tfl_car_parks,
    get_stop_car_parks,
    get_london_traffic_snapshot,
)

async def main():
    snap = await get_parking_and_charging_snapshot()
    print(json.dumps(snap, indent=2))
    avail = await get_ev_charge_connectors(status='Available', limit=3)
    print('available sample:', avail['connectors'])
    parks = await list_tfl_car_parks(limit=2)
    print('car parks sample:', parks['car_parks'])
    stop = await get_stop_car_parks('940GZZLUGFD')
    print('Greenford stop parks:', stop['car_park_count'])
    traffic = await get_london_traffic_snapshot()
    assert 'ev_charging' in traffic and 'car_parks' in traffic
    print('traffic snapshot includes ev_charging + car_parks: OK')

asyncio.run(main())
"
echo "Parking & charging test passed."
