# Heartbeat — NV-Disruptron 24/7 monitor

Run on every automated heartbeat (~10 minutes):

1. Read **USER.md** (mobility profile — do not repeat private fields aloud)
2. Call `disruptron_ops__get_london_city_briefing`
3. If user has EV (`USER.md` → `ev.enabled`):
   - Call `disruptron_ops__get_parking_and_charging_snapshot`
   - Compare EV availability near user's **areas** (not exact addresses)
   - Alert if available/total < user threshold (default 0.25) in any watched area
4. If user's **tube lines** (USER.md) not on good service → alert with equity note
5. If `congested_corridor_count` > 8 OR street closures > 15 → roads alert
6. Compare to **memory/YYYY-MM-DD.md** last snapshot — alert only if material change
7. Before TTS: apply **VOICE.md** — strip all PII from spoken text
8. If nothing material changed → reply `HEARTBEAT_OK` only

Material change = new line disruption, EV drop >10%, new corridor congestion, or user threshold crossed.
