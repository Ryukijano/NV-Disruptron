# Voice & TTS — privacy rules (ElevenLabs)

Apply to **every** spoken output (Talk Mode, `messages.tts`, heartbeat alerts).

## NEVER speak aloud

- Full postcodes or street addresses
- User name, phone, email, Telegram handle
- Calendar event titles, meeting names, attendee names
- License plates, payment info, OAuth tokens
- Exact GPS coordinates
- Contents of USER.md verbatim

## OK to speak

- Tube line names and delay severity
- Ward names (public deprivation context)
- EV connector counts: "246 of 349 chargers available citywide"
- Area labels from USER.md **labels only**: "near home", "near work", "on your usual route"
- Generic recommendations: "Consider delaying departure" not "Leave 42 Acme Street at 8:15"

## Rewrite pattern (text → speech)

1. Draft alert in text (can include detail for Telegram)
2. Create **spoken line** — max 3 sentences, 480 characters
3. Replace specific locations with "your area" / "near you"
4. Round numbers: "about seventy percent of chargers available"

## ElevenLabs persona

Config persona: `disruptron-public` (see OpenClaw `messages.tts.personas`)

If unsure whether text is safe to speak, **do not use TTS** — send text-only alert instead.
