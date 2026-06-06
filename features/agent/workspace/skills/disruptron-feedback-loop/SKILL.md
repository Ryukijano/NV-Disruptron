---
name: disruptron-feedback-loop
description: >-
  Close the agentic loop: MCP live data → workspace artifacts → read back →
  smarter next actions. Use for monitoring sessions, recurring analysis, or when
  prior metrics/reports should inform the current turn.
---

# NV-Disruptron feedback loop

## Loop diagram

```
MCP briefing → snapshot JSON → analyze_transport.py → metrics + report + CONTEXT.md
       ↑                                                      |
       └──────── read CONTEXT.md / latest.json on next turn ──┘
```

## Every monitoring turn

1. **Read** `analysis/CONTEXT.md` if it exists (prior stress score).
2. **Fetch** live data: `disruptron_ops__get_london_city_briefing` OR `fetch_briefing_snapshot.py`.
3. **Analyze** if user wants depth: `analyze_transport.py`.
4. **Compare** if prior snapshot exists: `compare_snapshots.py`.
5. **Act** — MCP drill-down driven by `metrics.latest.json` stress_score and deltas.
6. **Write** — update `memory/YYYY-MM-DD.md` with one-line state change.
7. **Reply** — Situation / Impact / Evidence / Recommended actions.

## Decision rules (from metrics)

| Condition | Next action |
|-----------|-------------|
| `stress_score` > 50 | Equity drill-down on worst tube line |
| `stress_score` delta up ≥ 10 | Alert user (channel skill) |
| `ev_available_ratio` < 0.3 | `get_ev_charge_summary` |
| `congested_corridors` ≥ 5 | `get_all_road_status(congested_only=true)` |
| `material_change` false in delta | Heartbeat: HEARTBEAT_OK |

## Session memory

- `memory/YYYY-MM-DD.md` — chronological log (human readable)
- `analysis/` — machine-readable artifacts for exec + read tools

Do not duplicate full JSON in memory files; point to `analysis/snapshots/latest.json`.
