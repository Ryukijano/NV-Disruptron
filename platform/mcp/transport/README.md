# TfL London MCP Server

MCP server that gives AI agents secure, structured access to the **Transport for London (TfL) Unified API** — public transport **and** live road traffic.

---

## Features (Current)

### Public transport
- `get_line_disruptions_by_mode(modes)` — `GET /Line/Mode/{modes}/Disruption`
- `get_line_disruptions(line_ids)` — `GET /Line/{ids}/Disruption`
- `get_line_status(line_ids)` / `get_line_status_by_mode(modes)`
- `get_lines_by_mode(modes)`, `list_line_modes()`
- `search_stops(query)`, `get_stop_arrivals(stop_id)`
- `plan_journey(from, to)`, `get_bike_points(lat, lon, radius)`
- `get_mode_arrivals(mode)` — live arrivals across a whole mode
- `get_stop_crowding(stop_id, line_id)`

### Road traffic & street works
- `get_london_traffic_snapshot()` — one-call Tube + road + street overview
- `get_all_road_status(congested_only)` — `GET /Road/all/Status` (all 24 corridors)
- `get_street_disruptions()` — `GET /Road/all/Street/Disruption` (requires date range; auto-today)
- `get_all_road_disruptions()` — `GET /Road/all/Disruption` (incidents/works by corridor)
- `get_road_status(road_ids)` — `GET /Road/{ids}/Status` (specific corridor congestion)
- `get_road_disruptions(road_ids)` — works/closures on specific A-roads
- `get_road_disruption_categories()` / `get_road_disruption_severities()` — TfL metadata
- `list_tfl_roads()` — discover road corridor IDs (a1, a406, inner ring, …)

### EV charging & car parks (retried 2026-06-06)
- `get_parking_and_charging_snapshot()` — **one-call** live EV + car park directory
- `get_ev_charge_summary()` — `GET /Occupancy/ChargeConnector` ✅ ~349 connectors live
- `get_ev_charge_connectors(status, limit)` — filter Available / Charging / OutOfService
- `get_ev_charge_connector(source_system_place_id)` — lookup by e.g. `ChargePointESB-UT06EL-3`
- `list_tfl_car_parks()` — `GET /Place/Type/CarPark` ✅ 58 parks (capacity, tariffs, hours)
- `get_car_park_detail(car_park_id)` — full metadata + occupancy attempt
- `get_car_park_occupancy(car_park_id)` — live bays; **TfL HTTP 500** → metadata fallback
- `get_stop_car_parks(stop_id)` — use Naptan e.g. `940GZZLUGFD` (not hub ID)

### Environment
- `get_air_quality()` — current London air quality forecast
- `get_tfl_api_status()` — check if your key is loaded

All tools return clean JSON from the official TfL API. **No API key required** for demo (anonymous ~50 req/min).

---

## Quick Start

### 1. Get a TfL API Key (Free)

1. Visit https://api-portal.tfl.gov.uk/
2. Sign up or sign in
3. Go to **Products** → subscribe to the free **"500 Requests per min"** product
4. Give the subscription a name (e.g. `nvidia-hack-tfl`)
5. Go to **Profile** and copy your `app_key`

**Note:** You only need the `app_key` now. `app_id` is deprecated.

### 2. Configure the Server

```bash
cd platform/mcp/transport
cp .env.example .env
# Edit .env and put your real key:
# TFL_APP_KEY=your_actual_key_here
```

### 3. Install & Run

Using **uv** (recommended, already present in this environment):

```bash
uv sync
uv run python server.py
```

Or using the MCP CLI (after sync):

```bash
uv run mcp run server.py
```

The server uses **stdio** transport by default — this is the standard way local agents connect to MCP servers.

---

## Connecting to Agents

### In this Grok Build environment

This workspace already supports MCP via the connected tools (`search_tool` / `use_tool`).  
After starting the server (or configuring it), you can discover and use the tools it exposes.

### Other common clients

- **Claude Desktop**: Add to `claude_desktop_config.json` under `mcpServers`
- **Cursor / Windsurf / Continue.dev**: Use the MCP server configuration in settings
- **Any MCP client**: Point it at `python server.py` or the installed command with stdio

Example Claude Desktop snippet (stdio):

```json
{
  "mcpServers": {
    "tfl-london": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/platform/mcp/transport", "run", "python", "server.py"],
      "env": {
        "TFL_APP_KEY": "your_key_here"
      }
    }
  }
}
```

You can also run it with `mcp run` if you prefer.

---

## Example Tool Calls (what agents will see)

**Live road traffic snapshot (start here):**
```
get_london_traffic_snapshot()
get_all_road_status(congested_only=true)
get_street_disruptions(closed_only=true, limit=10)
get_all_road_disruptions(limit=10, category="Works")
get_road_status(road_ids="a1,a406,inner ring")
```

**Tube disruptions:**
```
get_line_disruptions_by_mode(modes="tube")
get_line_disruptions(line_ids="jubilee")
```

**Discover IDs:**
```
list_tfl_roads()
get_lines_by_mode(modes="tube")
list_line_modes()
```

---

## Response Format

Tools return the raw (or very lightly processed) response from TfL so agents get accurate, up-to-date data.

Typical disruption fields:
- `description` — the main message agents should surface to users
- `category` — `RealTime`, `PlannedWork`, `Information`
- `closureText` — `partSuspended`, `plannedClosure`, etc.
- `affectedRoutes`, `affectedStops`
- timestamps

---

## TfL API reference (verified live)

| Endpoint | Tool |
|----------|------|
| `GET /Road/all/Status` | `get_all_road_status` |
| `GET /Road/all/Street/Disruption?startDate=&endDate=` | `get_street_disruptions` |
| `GET /Road/all/Disruption` | `get_all_road_disruptions` |
| `GET /Road/{ids}/Status` | `get_road_status` |
| `GET /Road/{ids}/Disruption` | `get_road_disruptions` |
| `GET /Road/Meta/Categories` | `get_road_disruption_categories` |
| `GET /Road/Meta/Severities` | `get_road_disruption_severities` |
| `GET /Road` | `list_tfl_roads` |
| `GET /AirQuality` | `get_air_quality` |
| `GET /Mode/{mode}/Arrivals` | `get_mode_arrivals` |
| `GET /StopPoint/{id}/Crowding/{line}` | `get_stop_crowding` |

Note: `GET /Road/all/Street/Disruption` **requires** `startDate` and `endDate` query params (404 without them). The MCP tool defaults to today UTC.

---

## Environment Variables

| Variable      | Required | Description                              |
|---------------|----------|------------------------------------------|
| `TFL_APP_KEY` | Recommended | Your TfL subscription key (500 req/min) |
| `TFL_APP_ID`  | Optional   | Legacy app ID (usually not needed)       |

Without `TFL_APP_KEY` the server still works but you are limited to the anonymous rate limit (~50 req/min).

---

## License / Attribution

Data provided by Transport for London Unified API.  
Please respect TfL's terms when using the data in production services.

---

## Next Steps (Ideas)

- Add a tool that returns a nice human summary instead of raw JSON
- Add arrival predictions (`/StopPoint/{id}/Arrivals`)
- Add journey planning wrapper
- Add SSE/HTTP transport option for remote deployment
- Add caching for frequently requested modes

Pull requests / ideas welcome during the hackathon!
