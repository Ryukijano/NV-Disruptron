# NV-Disruptron OpenClaw skills

Workspace skills teach the **disruptron** agent how to run autonomous London mobility workflows. Each skill is a folder with `SKILL.md` (YAML frontmatter + procedure).

OpenClaw loads these on session start from `features/agent/workspace/skills/`. After adding or editing skills:

```bash
openclaw gateway restart
openclaw skills list
```

## Skill catalog

| Skill | Use when |
|-------|----------|
| [disruptron-ops](disruptron-ops/SKILL.md) | **Default orchestrator** — broad London status |
| [disruptron-proactive-alert](disruptron-proactive-alert/SKILL.md) | Heartbeat alerts on material changes |
| [disruptron-ev-companion](disruptron-ev-companion/SKILL.md) | EV charging personalized to USER.md |
| [disruptron-voice](disruptron-voice/SKILL.md) | Talk Mode / spoken replies (VOICE.md) |
| [disruptron-vision-browser](disruptron-vision-browser/SKILL.md) | Browser screenshots + vision |
| [disruptron-multi-tool-analysis](disruptron-multi-tool-analysis/SKILL.md) | Chain MCP + web_fetch |
| [disruptron-deep-research](disruptron-deep-research/SKILL.md) | AI-Q reports via `:8001` sidecar |
| [disruptron-monitor](disruptron-monitor/SKILL.md) | Heartbeat, watch mode, investigations |
| [disruptron-tube](disruptron-tube/SKILL.md) | Named line, delays, closures |
| [disruptron-roads](disruptron-roads/SKILL.md) | Congestion, A-roads, street closures |
| [disruptron-parking-charging](disruptron-parking-charging/SKILL.md) | EV connectors, car parks |
| [disruptron-equity](disruptron-equity/SKILL.md) | IMD deprivation, worst affected |
| [disruptron-spatial](disruptron-spatial/SKILL.md) | Postcode → ward, ward profiles |
| [disruptron-channel-reply](disruptron-channel-reply/SKILL.md) | Telegram/mobile formatting |
| [disruptron-data-analysis](disruptron-data-analysis/SKILL.md) | Metrics, stress score, reports |
| [disruptron-programming](disruptron-programming/SKILL.md) | `exec` Python/shell in workspace |
| [disruptron-context-memory](disruptron-context-memory/SKILL.md) | SQLite recall, run_id/chat_id, cross-session memory |
| [disruptron-feedback-loop](disruptron-feedback-loop/SKILL.md) | MCP → artifacts → next turn |

## MCP tool naming

| Mode | Prefix | Set by |
|------|--------|--------|
| Slim (default) | `disruptron_ops__` | `DISRUPTRON_SLIM_MCP=true` |
| Full | `tfl_london__`, `london_impact__`, `london_spatial__` | `DISRUPTRON_SLIM_MCP=false` |

## Related workspace files

- `../AGENTS.md` — global autonomous loop
- `../TOOLS.md` — MCP tool reference
- `../HEARTBEAT.md` — monitor checklist
- `../USER.md` — private mobility profile
- `../VOICE.md` — TTS privacy constraints
