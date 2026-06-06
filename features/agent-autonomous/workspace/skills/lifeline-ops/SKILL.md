---
name: lifeline-ops
description: >-
  Primary orchestrator for autonomous London urban ops. Routes broad or ambiguous
  queries to the right LifeLine skill and MCP tools. Use first for "how's London",
  hackathon demos, or any question spanning tube, roads, EV, and equity.
---

# LifeLine ops (orchestrator)

## When to activate

- Broad or multi-domain London ops questions
- User intent unclear — route to a specialist skill after briefing
- Default entry point when no narrower skill matches

## Specialist skills (delegate after orient)

| Domain | Skill | Trigger |
|--------|-------|---------|
| Watch / heartbeat | `lifeline-monitor` | monitor, watch, what changed |
| Tube / rail | `lifeline-tube` | named line, delays, closures |
| Roads / streets | `lifeline-roads` | congestion, A-roads, street works |
| EV / parking | `lifeline-parking-charging` | chargers, car parks |
| Equity / IMD | `lifeline-equity` | deprived wards, who is affected |
| Wards / postcodes | `lifeline-spatial` | postcode, ward profile, IMD rank |

## Procedure

1. Run `lifeline_ops__get_london_city_briefing`.
2. Parse `summary`, `live_transport`, `parking_and_charging`, `equity_impact`.
3. Pick the dominant issue; apply the matching specialist skill's drill-down.
4. Synthesize **Situation → Impact → Evidence → Recommended actions**.

## MCP tool prefix

- **Slim (default):** `lifeline_ops__*`
- **Full catalog:** `NEMOCLAW_SLIM_MCP=false` → `tfl_london__*`, `london_impact__*`, `london_spatial__*`

## Do not

- Answer from training data about current delays
- Call the same tool twice with identical parameters in one turn
- Claim car park bay occupancy when API status is not live
