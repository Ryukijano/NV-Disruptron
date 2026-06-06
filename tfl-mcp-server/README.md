# TfL London MCP Server

MCP server that gives AI agents (Grok, Claude, Cursor, etc.) secure, structured access to the **Transport for London (TfL) Unified API**, starting with line disruptions.

**Primary focus (as requested):**
- `GET /Line/Mode/{modes}/Disruption` → `get_line_disruptions_by_mode`
- Also includes the per-line version for "a particular line": `GET /Line/{ids}/Disruption`

---

## Features (Current)

- `get_line_disruptions_by_mode(modes)` — Exact match to the API operation you linked
- `get_line_disruptions(line_ids)` — Best for specific lines (victoria, jubilee, northern, etc.)
- `get_lines_by_mode(modes)` — Discover line IDs
- `list_line_modes()` — See available modes
- `get_tfl_api_status()` — Check if your key is loaded

All tools return clean JSON from the official TfL API.

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
cd tfl-mcp-server
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
      "args": ["--directory", "/absolute/path/to/tfl-mcp-server", "run", "python", "server.py"],
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

**Get disruptions for the entire Tube network:**
```
get_line_disruptions_by_mode(modes="tube")
```

**Get disruptions for specific lines only:**
```
get_line_disruptions(line_ids="jubilee")
get_line_disruptions(line_ids="northern,central,piccadilly")
```

**Discover what lines exist:**
```
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

## Development & Extension

The server is intentionally small and easy to extend.

Want to add more TfL endpoints later?
- Status by mode: `/Line/Mode/{modes}/Status`
- StopPoint arrivals
- Journey planning
- etc.

Just add new `@mcp.tool()` functions that call `_tfl_get(...)`.

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
