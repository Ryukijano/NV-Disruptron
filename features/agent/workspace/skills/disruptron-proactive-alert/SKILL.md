---
name: disruptron-proactive-alert
description: >-
  Decide when NV-Disruptron should interrupt the user 24/7 (text + ElevenLabs audio).
  Compare live API snapshots to USER.md thresholds and recent memory. Apply VOICE.md
  before any spoken alert.
---

# Proactive 24/7 alerts

## When to alert (not HEARTBEAT_OK)

| Signal | Condition |
|--------|-----------|
| Tube | User's `transport.usual_lines` not good service |
| EV | Availability < `ev.min_availability_ratio` near watched areas |
| Roads | Commute-corridor congestion spike (briefing roads section) |
| Equity | New high-IMD ward exposure on user's lines |
| City stress | Analysis pipeline stress score up >15% vs last memory |

## Delivery

1. **Text first** — Telegram / last channel / Control UI (full detail OK in text)
2. **Voice second** — if `ELEVENLABS_API_KEY` set and `messages.tts.auto` is active:
   - Rewrite alert through VOICE.md (max 480 chars)
   - Do not paste raw tool JSON into TTS

## Anti-spam

- Same alert class: max once per 30 minutes unless severity worsens
- Log last alert in `memory/YYYY-MM-DD.md`
- Overnight (23:00–06:00): only critical (line suspended, EV <10% near home)

## Message tool

Use OpenClaw `message` to push to configured channels when heartbeat detects material change.
