# User mobility profile (PRIVATE — agent context only)

Edit this file so NV-Disruptron can personalize 24/7 alerts. **Never read these fields aloud** — see VOICE.md.

## Identity (text alerts OK, voice NO)

- Name: (leave blank or first name only)
- Telegram user id: (for channel routing)


```yaml
ev:
  enabled: true
  min_availability_ratio: 0.25
  areas:
    - label: "E15"
      ward_or_postcode_prefix: "E15"
```


```yaml
transport:
  usual_lines: ['central']
  areas:
    - label: "E15"
      ward_or_postcode_prefix: "E15"
  alert_on:
    line_disruption: true
    road_congestion_on_commute: true
```


```yaml
activity:
  morning_commute_window: "07:00-09:30"
  evening_commute_window: "17:00-19:30"
```

## Deployment

- Project: **NV-Disruptron** — Hack for Impact London 2026
- Stack: local DGX Spark, vLLM Nemotron, OpenClaw gateway, ElevenLabs TTS (optional)

## Transport (synced from web onboarding)

```yaml
transport:
  usual_lines: ['central', 'jubilee']
  areas:
    - label: "E15"
      ward_or_postcode_prefix: "E15"
    - label: "EC2"
      ward_or_postcode_prefix: "EC2"
  alert_on:
    line_disruption: true
    road_congestion_on_commute: true
```
