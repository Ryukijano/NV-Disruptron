---
name: disruptron-multi-tool-analysis
description: >-
  Chain multiple MCP tools and optional web_fetch for cross-source London
  analysis. Use when the answer requires comparing live APIs, ward data, and
  public documentation — not a single tool call.
---

# Multi-tool London analysis

## When to activate

- User needs **comparison** (lines, wards, corridors, time periods)
- Answer requires **3+ tool calls** across transport + spatial + impact
- User references **APIs or data sources** (TfL, IMD, GLA, data.london.gov.uk)
- Before escalating to `disruptron-deep-research`

## Standard analysis chain

1. **Orient** — `disruptron_ops__get_london_city_briefing`
2. **Scope** — pick domain from triage (tube / roads / EV / equity)
3. **Drill** — 2–4 targeted tools (never repeat identical args):
   - Tube line → `score_line_disruption_impact`
   - Roads → `get_all_road_status` + `get_street_disruptions`
   - EV → `get_ev_charge_summary` + `get_parking_and_charging_snapshot`
   - Ward → `lookup_ward_by_postcode` or `get_ward_profile`
   - Full snapshot → `get_london_traffic_snapshot`
4. **Optional public docs** — `web_fetch` for stable references only:
   - `https://api.tfl.gov.uk/` (API docs)
   - `https://data.london.gov.uk/` (dataset context)
   - Do **not** scrape paywalled or login pages
5. **Synthesize** — cross-reference tool JSON; note contradictions honestly
6. **Optional metrics** — `./scripts/run_analysis_pipeline.sh` then read `analysis/metrics/latest.json`

## Step budget

- Max **8** tool steps per turn (including web_fetch)
- Max **2** identical tool+args per turn
- Stop and summarize if rate-limited or tool errors

## Output

Always use: **Situation → Impact → Evidence (bullets with source) → Recommended actions**

If evidence is incomplete, say what you could not fetch and which tool failed.
