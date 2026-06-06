## Learned User Preferences

- Branding is **NV-Disruptron** only — no legacy aliases in docs or scripts.
- 24/7 autonomous monitor with proactive text + ElevenLabs voice alerts; privacy-safe TTS (no PII in speech).
- EV/charging companion personalized via `features/agent/workspace/USER.md` activity profile.
- Local vLLM Nemotron + OpenClaw gateway; optional AI-Q deep research on `:8001`.
- Web delivery UI lives under `features/delivery/web/` (React + Vite); gateway at `features/delivery/disruptron-api/`.

## Learned Workspace Facts

- Repo `/home/nvidia/NV-Disruptron`; launch: `./scripts/disruptron daemon` (24/7) or `./scripts/disruptron run` (interactive).
- OpenClaw agent id: `disruptron`; MCP prefix: `disruptron_ops__*`; heartbeat every 10m default.
- Voice: `messages.tts` ElevenLabs persona `disruptron-public`; rules in `features/agent/workspace/VOICE.md`.
- Key tools: `get_london_city_briefing`, `get_parking_and_charging_snapshot`, `get_ev_charge_summary`.
- TfL transport MCP path: `platform/mcp/transport/`.
