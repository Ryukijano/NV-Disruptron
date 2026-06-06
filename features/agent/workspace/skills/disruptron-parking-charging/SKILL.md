---
name: disruptron-parking-charging
description: >-
  London EV charging availability and TfL car park intelligence. Use when the
  user asks about EV chargers, connectors, charging bays, car parks, parking
  near stations, or "how many chargers are available".
---

# NV-Disruptron parking & charging

## When to activate

- "How many EV chargers are available?"
- "Car parks near Greenford station"
- "Is EV charging stressed right now?"
- Parking/charging leg of a multimodal journey

## Procedure (slim MCP — default)

1. Start with `disruptron_ops__get_parking_and_charging_snapshot` or read counts from briefing.
2. For EV stress detail → `disruptron_ops__get_ev_charge_summary`.
3. Report from tool fields:
   - **EV**: `available`, `charging`, `out_of_service`, `total_connectors`
   - **Car parks**: `total_car_parks`, `total_listed_spaces`, `live_occupancy_api_status`

## Full MCP mode (DISRUPTRON_SLIM_MCP=false)

Use `tfl_london__*` tools:

| Need | Tool |
|------|------|
| Filter available connectors | `get_ev_charge_connectors(status='Available')` |
| Single connector | `get_ev_charge_connector` |
| Car park list | `list_tfl_car_parks` |
| Park at station | `get_stop_car_parks` with **Naptan** id (`940GZZLUxxx`, not hub id) |
| Tariffs / hours | `get_car_park_detail` |

## Known TfL limits

- `GET /Occupancy/ChargeConnector` — **live** ✅ (~349 connectors)
- `GET /Occupancy/CarPark` — **HTTP 500** on TfL side ❌
- Car park **metadata** via `Place/Type/CarPark` — **live** ✅ (58 sites, 8340 spaces)

## Output format

- State live vs metadata-only data honestly
- If EV availability ratio < 30%, flag as operational stress
- Note car parks are directory metadata unless occupancy API recovers

## Smoke test (no LLM)

```bash
/home/nvidia/NV-Disruptron/scripts/test_parking_charging.sh
```
