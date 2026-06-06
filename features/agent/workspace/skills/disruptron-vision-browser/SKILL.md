---
name: disruptron-vision-browser
description: Use browser automation and Nemotron Omni vision for live web analysis and screenshots.
---

# Vision + browser automation

Use when the user asks to **look at a website**, verify a live page, or analyze visual UI state.

## Workflow

1. `browser` → check status / open tab
2. `browser navigate` → target URL (TfL status, EV maps, news)
3. `browser snapshot` → structured page refs
4. `browser screenshot` → image for Nemotron Omni vision (preferred for layout/maps)
5. `browser act` → click/type only when snapshot refs are stable
6. Summarize findings with MCP evidence where applicable

## Rules

- Prefer **screenshot + vision** for maps, charts, and dense UI; use snapshot for forms/links
- Resnapshot after navigation or modal dialogs
- Report login/2FA/captcha blockers — do not guess credentials
- Apply **VOICE.md** if summarizing aloud; never speak URLs with tokens or private query params
- Chain `disruptron_ops__*` tools after visual checks for quantitative London/EV claims

## Profiles

- Default: `openclaw` (isolated managed browser)
- `user` profile only when the human is present to approve attach to signed-in Chrome
