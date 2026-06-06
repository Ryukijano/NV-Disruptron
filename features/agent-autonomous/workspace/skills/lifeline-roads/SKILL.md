---
name: lifeline-roads
description: >-
  London road congestion, A-road corridor status, and street disruption
  intelligence. Use for traffic jams, road closures, street works, congested
  corridors, or "which roads are bad right now".
---

# LifeLine roads & streets

## When to activate

- "Which A-roads are congested?"
- "Any street closures in central London?"
- "Road disruption status"
- Briefing shows high `congested_corridor_count` or street closure count

## Procedure

1. Orient: `lifeline_ops__get_london_city_briefing` or `lifeline_ops__get_london_traffic_snapshot`.
2. **Corridor congestion** → `lifeline_ops__get_all_road_status(congested_only=true)`.
   - Report corridor names, severity (`Serious`, `Moderate`, …), active disruption count.
3. **Street works / closures** → `lifeline_ops__get_street_disruptions`.
   - Default date window is today UTC (MCP handles `startDate`/`endDate`).
   - Summarize `closed_or_restricted_count` and worst segments by severity.
4. Cross-link equity if closures cluster in deprived boroughs (optional ward lookup).

## Full MCP mode

- `tfl_london__get_road_status` / `get_road_disruptions` for specific road ids
- `tfl_london__get_all_road_disruptions` for incident-level detail (~80 active)

## TfL quirk

`GET /Road/all/Street/Disruption` returns **404** without date parameters. The MCP server always supplies today's window.

## Output format

- Separate **corridor congestion** (flow) from **street disruptions** (closures/works)
- Name top 3 corridors or segments with severity
- Recommended actions: which corridor to drill into, whether to alert borough ops
