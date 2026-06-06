---
name: disruptron-ev-companion
description: >-
  Autonomous EV and car-charging companion. Monitors TfL charge connectors and
  car parks near the user's areas (from USER.md). Proactive alerts when
  availability drops or citywide EV stress rises. Never speak payment or location PII.
---

# EV companion (autonomous)

## When to activate

- Heartbeat with `USER.md` → `ev.enabled: true`
- User asks about charging, range anxiety, "can I charge near…"
- Within `activity.pre_trip_ev_check_minutes` of commute windows

## Procedure

1. Read USER.md EV section (areas as ward/postcode **prefix** for tool lookup only)
2. `disruptron_ops__get_parking_and_charging_snapshot`
3. `disruptron_ops__get_ev_charge_summary`
4. If user area known → `disruptron_ops__lookup_ward_by_postcode` (prefix) for equity context
5. Compare `available/total` to `ev.min_availability_ratio`
6. If below threshold → **proactive alert** (text + voice per VOICE.md)

## Alert templates

**Text (Telegram/UI):**
```text
EV alert: Citywide 246/349 connectors available (70%). Near home area: low availability — consider alternate charge point.
```

**Voice (after VOICE.md scrub):**
```text
Heads up — EV charging near you is tighter than usual. About sixty percent of connectors are free citywide. I'd charge before your evening trip if you can.
```

## Autonomous vehicle hooks

- Before commute windows: run EV check even if city briefing is quiet
- On rapid citywide drop (>10% in one heartbeat): alert all EV users
- Pair with `disruptron-proactive-alert` for delivery

## Tools

- `disruptron_ops__get_parking_and_charging_snapshot`
- `disruptron_ops__get_ev_charge_summary`
- `disruptron_ops__lookup_ward_by_postcode`
- `disruptron_ops__get_ward_profile`
