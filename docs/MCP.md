# MCP tool reference

All MCP servers live under **`platform/mcp/`**. OpenClaw uses the slim ops package by default.

| Directory | OpenClaw id | Tools |
|-----------|-------------|-------|
| `platform/mcp/ops` | `disruptron_ops` | 12 (slim, default) |
| `platform/mcp/transport` | `tfl_london` | ~31 |
| `platform/mcp/spatial` | `london_spatial` | 7 |
| `platform/mcp/impact` | `london_impact` | 7 |

Shortcut from repo root: `mcp/` → `platform/mcp/` (e.g. `mcp/spatial`, `mcp/impact`).

## TfL Transport (`platform/mcp/transport`)

Tube, roads, EV charging, car parks — live TfL Unified API.

Key tools: `get_london_traffic_snapshot`, `get_parking_and_charging_snapshot`, `get_ev_charge_summary`, `get_all_road_status`, `get_street_disruptions`.

## London Spatial (`platform/mcp/spatial`)

Wards, IMD 2019 deprivation, postcode geocoding.

Key tools: `lookup_ward_by_postcode`, `get_ward_profile`, `search_wards`.

## London Impact (`platform/mcp/impact`)

Composite briefing and equity-weighted disruption scoring.

Key tools: `get_london_city_briefing`, `score_line_disruption_impact`.

## Disruptron Ops (`platform/mcp/ops`)

Slim re-export for OpenClaw — prefix `disruptron_ops__*`.

Start here: `disruptron_ops__get_london_city_briefing`

Shared Python: `platform/shared/tfl_client.py`, `disruptron_data.py`.

Optional `TFL_APP_KEY` in repo `.env` for higher rate limits.

See [platform/mcp/README.md](../platform/mcp/README.md).
