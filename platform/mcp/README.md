# MCP servers

All Model Context Protocol servers for NV-Disruptron live under `platform/mcp/`.

| Package | Directory | OpenClaw id | Tools |
|---------|-----------|-------------|-------|
| **Ops (slim)** | `ops/` | `disruptron_ops` | 9 — default for 24/7 agent |
| **Transport** | `transport/` | `tfl_london` | ~31 — tube, roads, EV, car parks |
| **Spatial** | `spatial/` | `london_spatial` | 7 — wards, IMD, postcodes |
| **Impact** | `impact/` | `london_impact` | 7 — briefing, equity scoring |

## Setup

```bash
./scripts/disruptron setup
# or per package:
cd platform/mcp/ops && uv sync
```

## Run standalone (debug)

```bash
cd platform/mcp/transport && uv run python server.py
cd platform/mcp/spatial && uv run python server.py
cd platform/mcp/impact && uv run python server.py
cd platform/mcp/ops && uv run python server.py
```

## Repo root shortcut

`mcp/` is a symlink to this directory — use `mcp/spatial` or `mcp/impact` from the repo root if you prefer shorter paths.

The slim **ops** server re-exports tools from transport, spatial, and impact for low-context OpenClaw sessions.

Shared Python: `platform/shared/` · Docs: [docs/MCP.md](../../docs/MCP.md)
