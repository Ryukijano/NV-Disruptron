# LifeLine OpenClaw skills

Workspace skills teach the **lifeline** agent how to run autonomous London ops workflows. Each skill is a folder with `SKILL.md` (YAML frontmatter + procedure).

OpenClaw loads these on session start from `nemoclaw/workspace/skills/`. After adding or editing skills:

```bash
openclaw gateway restart
# or start a new session: /new in TUI
openclaw skills list
```

## Skill catalog

| Skill | Use when |
|-------|----------|
| [lifeline-ops](lifeline-ops/SKILL.md) | **Default orchestrator** — broad London status, multi-domain demos |
| [lifeline-monitor](lifeline-monitor/SKILL.md) | Heartbeat, watch mode, "what to investigate next" |
| [lifeline-tube](lifeline-tube/SKILL.md) | Named line, delays, closures, good service |
| [lifeline-roads](lifeline-roads/SKILL.md) | Congestion, A-roads, street closures |
| [lifeline-parking-charging](lifeline-parking-charging/SKILL.md) | EV connectors, car parks |
| [lifeline-equity](lifeline-equity/SKILL.md) | IMD deprivation, who is worst affected |
| [lifeline-spatial](lifeline-spatial/SKILL.md) | Postcode → ward, ward profiles |
| [lifeline-channel-reply](lifeline-channel-reply/SKILL.md) | Telegram/mobile formatting |
| [lifeline-data-analysis](lifeline-data-analysis/SKILL.md) | Metrics, stress score, reports |
| [lifeline-programming](lifeline-programming/SKILL.md) | `exec` Python/shell in workspace |
| [lifeline-feedback-loop](lifeline-feedback-loop/SKILL.md) | MCP → artifacts → next turn |

## MCP tool naming

| Mode | Prefix | Set by |
|------|--------|--------|
| Slim (default) | `lifeline_ops__` | `NEMOCLAW_SLIM_MCP=true` in configure script |
| Full | `tfl_london__`, `london_impact__`, `london_spatial__` | `NEMOCLAW_SLIM_MCP=false` |

## Example prompts per skill

```text
# lifeline-ops / lifeline-monitor
Monitor London and tell me the top 3 things to investigate next

# lifeline-tube
Piccadilly line is disrupted — which deprived wards are most exposed?

# lifeline-roads
Which road corridors are seriously congested right now?

# lifeline-parking-charging
How many EV chargers are available vs out of service?

# lifeline-equity
Score District line disruption impact on vulnerable wards

# lifeline-spatial
What ward is E15 4HT and what's its IMD rank?
```

## Related workspace files

- `../AGENTS.md` — global autonomous loop (always loaded)
- `../TOOLS.md` — MCP tool reference
- `../HEARTBEAT.md` — short checklist for automated monitors
