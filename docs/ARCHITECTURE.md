# Architecture

## Runtime

**NV-Disruptron** uses a single OpenClaw agent (`disruptron`) backed by local **vLLM** Nemotron at `http://127.0.0.1:8000/v1`.

| Mode | Entry | Behavior |
|------|-------|----------|
| **Daemon** | `./scripts/disruptron daemon` | 24/7 heartbeat, proactive alerts, voice |
| **Interactive** | `./scripts/disruptron run` | TUI, Talk Mode, vision, browser |
| **One-shot** | `./scripts/disruptron query "…"` | Single agent turn |

## Platform layout

| Component | Path |
|-----------|------|
| Slim ops MCP | `platform/mcp/ops/` |
| Full MCP servers | `platform/mcp/{transport,spatial,impact}/` |
| Push API | `platform/delivery/outputs-api/` |
| Shared Python | `platform/shared/` |
| Agent workspace | `features/agent/workspace/` |

## MCP services

| Path | Role |
|------|------|
| `platform/mcp/ops` | Slim 9-tool subset (OpenClaw default) |
| `platform/mcp/transport` | Live TfL: tube, roads, EV, car parks |
| `platform/mcp/spatial` | Wards, IMD 2019, geocoding |
| `platform/mcp/impact` | Briefing, equity scoring |

Shortcut: `mcp/` → `platform/mcp/` (e.g. `mcp/spatial`, `mcp/impact`).

See [platform/mcp/README.md](../platform/mcp/README.md).

## Agentic feedback loop

1. MCP `disruptron_ops__get_london_city_briefing`
2. `workspace/scripts/run_analysis_pipeline.sh` → metrics + `analysis/CONTEXT.md`
3. Next turn reads artifacts → targeted drill-down
4. Heartbeat every 10m (`DISRUPTRON_HEARTBEAT_EVERY`)

## Channels

- **Interactive**: OpenClaw `channels.telegram` → `disruptron` agent
- **Push-only**: `platform/delivery/outputs-api` → Telegram

See [../features/agent/docs/CHANNELS.md](../features/agent/docs/CHANNELS.md).
