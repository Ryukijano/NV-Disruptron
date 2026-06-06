---
name: disruptron-voice
description: >-
  ElevenLabs / Talk Mode replies for NV-Disruptron. Short spoken alerts without
  leaking USER.md private fields. Always read VOICE.md first.
---

# Voice output (ElevenLabs)

See **VOICE.md** for full privacy rules.

## When to activate

- Talk Mode on paired OpenClaw app (Android/iOS/macOS)
- `messages.tts.auto: always` (daemon alerts)
- User requests verbal update

## Spoken alert shape

1. One-sentence headline
2. Two supporting facts (numbers OK, no addresses)
3. One recommended action

Max ~480 characters for TTS.

## Example

User profile: home E15, Jubilee line user, EV enabled.

**Bad (leaks PII):**
"Jubilee delay affects E15 4HT and your meeting at Acme Corp at 9am."

**Good:**
"Jubilee line has delays. Your usual tube is affected. EV charging near home is about sixty percent available. Consider leaving a bit earlier or charging before you go."
