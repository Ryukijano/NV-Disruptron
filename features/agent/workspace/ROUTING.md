# Agent routing (web + API)

Dual-path routing is implemented in `disruptron_api/backend/router.py` and documented here.

| Intent | Route | OpenClaw agent | Prefetch MCP briefing |
|--------|-------|----------------|----------------------|
| Quick Q&A, voice, image | `interactive` | `disruptron` | no |
| Morning plan / digest | `digest` | `disruptron` | yes |
| Monitor, investigate, equity, "how's London" | `autonomous` | `disruptron` | yes |
| Long message (>240 chars) | `autonomous` | `disruptron` | yes |

Web UI receives SSE `mode` events during `/v1/chat/stream`. Tool progress uses SSE `tool` and `ui` events from live `disruptron_ops__get_london_city_briefing`.

Configure autonomous agent: `DISRUPTRON_AUTONOMOUS_AGENT_ID=disruptron` (default).
