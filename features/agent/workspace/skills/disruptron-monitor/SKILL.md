---
name: disruptron-monitor
description: >-
  Periodic London transport monitoring and change detection. Use for heartbeat
  prompts, "watch London", "what changed since last check", ops dashboards, or
  when the user wants ongoing surveillance without naming specific tools.
---

# NV-Disruptron monitor

## When to activate

- "Monitor London" / "watch transport"
- Heartbeat or cron-driven status checks
- "What should we investigate next?"
- Demo: autonomous ops controller loop

## Procedure

1. Call `disruptron_ops__get_london_city_briefing`.
2. Compare against prior context (session memory or `memory/YYYY-MM-DD.md` if present).
3. Flag **only material changes**: new line disruptions, congestion spike, EV outage cluster, new street closures.
4. If nothing material changed and this is a heartbeat → reply `HEARTBEAT_OK` (one line) unless the user asked for a full report.
5. Otherwise output **Situation → Impact → Evidence → Recommended actions** (top 3 investigations).

## Thresholds (triage hints)

| Signal | Investigate when |
|--------|------------------|
| Tube lines not good service | ≥ 1 line → note equity_impact wards |
| Congested corridors | ≥ 5 serious → `disruptron_ops__get_all_road_status` |
| Street closures | ≥ 10 closed/restricted → `disruptron_ops__get_street_disruptions` |
| EV out of service | ≥ 15 or >10% of total → `disruptron_ops__get_ev_charge_summary` |

## Do not

- Invent delays or counts from memory
- Repeat identical briefing calls in the same turn
- Claim car park bay occupancy is live (TfL `Occupancy/CarPark` often HTTP 500)
