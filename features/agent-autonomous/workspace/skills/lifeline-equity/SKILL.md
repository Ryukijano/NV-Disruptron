---
name: lifeline-equity
description: >-
  London transport disruption equity and IMD deprivation analysis. Use when the
  user asks about deprived wards, vulnerability, economic exposure, "who is
  worst affected", line impact scoring, or hackathon equity demos.
---

# LifeLine equity impact

## When to activate

- "Which deprived wards are affected by the Jubilee delay?"
- "Equity impact of District line disruption"
- "Who bears the burden of this closure?"
- Hackathon: economic exposure + IMD ranking along a line

## Procedure

1. If line unknown → `lifeline_ops__get_london_city_briefing` and read `equity_impact`.
2. For a specific line → `lifeline_ops__score_line_disruption_impact(line_id)`  
   Line ids: lowercase TfL ids (`piccadilly`, `district`, `jubilee`, `northern`, …).
3. Highlight:
   - `top_impacted_wards` (ward name, IMD rank, population)
   - `severity_weight` and disruption status
4. For postcode/ward context → `lifeline_ops__lookup_ward_by_postcode` or `get_ward_profile`.
5. Synthesize: **who is affected, why they are vulnerable (IMD), operational priority**.

## Full MCP mode only (NEMOCLAW_SLIM_MCP=false)

Additional tools on `london_impact__*` / `london_spatial__*`:

- `compare_lines_disruption_impact`, `rank_vulnerable_wards_on_line`
- `rank_most_deprived_wards`, `map_line_to_wards`

## Output format

- Name the line and current TfL status (from tool result)
- Top 3 wards with IMD rank (lower rank = more deprived in IMD 2019)
- One sentence on commuter/service access impact
- Recommended follow-up (monitor line, alert borough, etc.)

## Do not

- Guess IMD ranks or ward names without a tool call
- Treat higher IMD rank number as "more deprived" (IMD rank 1 = most deprived)
