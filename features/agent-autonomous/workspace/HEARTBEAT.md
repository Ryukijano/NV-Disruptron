# Heartbeat checklist (keep short)

If this is an automated heartbeat or "monitor London" prompt:

1. Call `lifeline_ops__get_london_city_briefing`
2. If any tube line ≠ good service → note top vulnerable ward per affected line
3. If congested_corridor_count > 5 → flag for `lifeline_ops__get_all_road_status`
4. If EV available/total < 0.3 → flag for `lifeline_ops__get_ev_charge_summary`
5. Reply only if something changed since last check OR user asked for a report; otherwise HEARTBEAT_OK
