---
name: disruptron-channel-reply
description: >-
  Format NV-Disruptron responses for Telegram, WhatsApp, and other messaging channels.
  Use when replying on mobile chat surfaces — keep answers short, scannable, and
  under 3800 characters without raw JSON dumps.
---

# Channel-friendly replies

## When to activate

- User message arrived via Telegram, WhatsApp, Signal, Discord, or similar
- Heartbeat delivery to `target: last` (mobile alert)
- User asks for a "quick update" or "TL;DR"

## Format rules

1. **Lead with the headline** — one sentence Situation (numbers included).
2. **Bullets over paragraphs** — max 5 bullets for Evidence.
3. **Top 3 Recommended actions** — numbered, each one line.
4. **No raw JSON** — never paste tool payloads; extract human-readable fields only.
5. **Length cap** — stay under **3800 characters** (Telegram limit 4096).
6. **Bold sparingly** — use `**Situation**` section headers only; Telegram supports Markdown subset.

## Template

```text
**Situation** — …

**Impact** — …

**Evidence**
- Tube: …
- Roads: …
- EV: …

**Next**
1. …
2. …
3. …
```

## Heartbeat on channels

- Material change → short alert (no HEARTBEAT_OK wrapper).
- No change → `HEARTBEAT_OK` only.

## Do not

- Dump full ward tables or connector lists (offer "ask for detail on line X" instead)
- Use code blocks for tool output on mobile
