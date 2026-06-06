---
name: lifeline-tube
description: >-
  London Tube and rail line disruption status with equity follow-up. Use when
  the user names a specific line, asks about delays, closures, "good service",
  or multimodal status for tube/overground/elizabeth-line.
---

# LifeLine Tube & rail

## When to activate

- "Jubilee line status"
- "Which tube lines have delays?"
- "Piccadilly closure — who is affected?"
- Briefing `lines_not_good_service` is non-empty

## Procedure

1. Broad: `lifeline_ops__get_london_city_briefing` → read `live_transport.tube`.
2. Specific line equity: `lifeline_ops__score_line_disruption_impact(line_id)`.
3. Deeper snapshot: `lifeline_ops__get_london_traffic_snapshot` if roads/EV context needed too.

## Line id examples

| User says | line_id |
|-----------|---------|
| Jubilee | `jubilee` |
| Piccadilly | `piccadilly` |
| District | `district` |
| Northern | `northern` |
| Central | `central` |
| Elizabeth line | `elizabeth` |
| Waterloo & City | `waterloo-city` |

## Full MCP mode

- `tfl_london__get_line_status` / `get_line_disruptions`
- `tfl_london__get_line_status_by_mode(modes='tube')`
- `london_impact__compare_lines_disruption_impact` for multi-line compare

## Output format

- Line name + TfL status text (from tool, not memory)
- Active disruption count
- Top vulnerable ward (IMD) when equity tool was called
- Recommended: monitor, alternate routes, borough alert
