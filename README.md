# NV-Disruptron (Disruptron-Gyana)

**Autonomous London mobility intelligence** — NVIDIA Hack for Impact London 2026.

NV-Disruptron runs **24/7**, watches live TfL and EV charging APIs, and **proactively alerts** you by text and **ElevenLabs voice** when transport or charging conditions change for *your* mobility profile.

### Run 24/7 (autonomous)

```bash
./scripts/disruptron daemon
```

### Talk to the agent (interactive + voice + vision)

```bash
./scripts/disruptron run
```

Voice: OpenClaw Talk Mode or send a voice note (ElevenLabs Scribe → Nemotron Omni).  
Vision: attach an image or ask the agent to browse and screenshot a page.

1. Copy `.env.example` → `.env` and set `ELEVENLABS_API_KEY`, `VLLM_MULTIMODAL=1`
2. `./scripts/disruptron vllm --recreate` — enable Nemotron Omni audio/image in vLLM
3. Edit `features/agent/workspace/USER.md` with your EV/commute areas (kept private in voice output)
4. Pair OpenClaw mobile app → Talk Mode for hands-free voice

Install as systemd user service:

```bash
./scripts/disruptron install
systemctl --user enable --now nv-disruptron.service
```
