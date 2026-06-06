# User mobility profile (PRIVATE — agent context only)

Edit this file so NV-Disruptron can personalize 24/7 alerts. **Never read these fields aloud** — see VOICE.md.

## Identity (text alerts OK, voice NO)

- Name: (leave blank or first name only)
- Telegram user id: (for channel routing)

## EV / autonomous vehicle

```yaml
ev:
  enabled: true
  vehicle_type: "ev"          # ev | phev | watching_only
  connector_types: ["type2", "ccs"]
  min_availability_ratio: 0.25   # alert when below 25% available nearby
  areas:
    - label: "home"              # spoken as "near home" only
      ward_or_postcode_prefix: "E15"   # agent uses for spatial lookup, NOT for TTS
    - label: "work"
      ward_or_postcode_prefix: "EC2"
  notify_when:
    - low_availability_near_home
    - low_availability_near_work
    - rapid_drop_citywide      # >10% drop in one heartbeat
```

## Transport habits

```yaml
transport:
  usual_lines: ["jubilee", "central", "elizabeth-line"]
  usual_modes: ["tube", "bus"]
  areas:
    - label: "home"
      ward_or_postcode_prefix: "E15"
    - label: "work"
      ward_or_postcode_prefix: "EC2"
  alert_on:
    - line_disruption: true
    - road_congestion_on_commute: true
    - equity_spike_on_usual_lines: true
```

## Activity-based prompting

```yaml
activity:
  # Agent infers from time + calendar MCP (optional) — never speak event titles
  morning_commute_window: "07:00-09:30"
  evening_commute_window: "17:00-19:30"
  pre_trip_ev_check_minutes: 45    # before commute, check chargers if EV enabled
```

## Deployment

- Project: **NV-Disruptron** — Hack for Impact London 2026
- Stack: local DGX Spark, vLLM Nemotron, OpenClaw gateway, ElevenLabs TTS (optional)
