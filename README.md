# NV-Disruptron

**Autonomous London mobility intelligence** — NVIDIA Hack for Impact London 2026.

NV-Disruptron runs **24/7**, watches live TfL, EV charging, and CCTV feeds, and **proactively alerts** you by text and **ElevenLabs voice** when transport or charging conditions change for *your* mobility profile.

## Features

| Feature | Description |
|---------|-------------|
| **Dynamic Route Planning** | Ask "route me from X to Y" — fetches live TfL journey plans and streams route coordinates to the map |
| **CCTV Monitoring** | Browse 200+ TfL JamCams, click to analyze with **LocateAnything-3B** for real-time object detection (cars, buses, pedestrians, bicycles) |
| **Video Stream Analysis** | Temporal object tracking across sampled frames — filters out transient objects, keeps persistent detections |
| **GPU-Optimized Inference** | Both **LocateAnything-3B** and **Nemotron Omni** run on GPU simultaneously (~48 GB / 128 GB) |
| **Parallel Box Decoding** | LocateAnything uses **hybrid PBD** — parallel block decoding for speed, AR fallback for accuracy |
| **RAPIDS GPU Analytics** | cuDF ETL, cuSpatial joins, cuGraph network analysis, cuML clustering on live hazard data |
| **24/7 Autonomous Monitor** | Proactive alerts via text + ElevenLabs voice when conditions change |
| **OpenClaw Agent** | Natural language chat with multimodal reasoning (text, image, audio) via Nemotron Omni |

## Quick Start

### Prerequisites

- NVIDIA GPU (tested on DGX Spark GB10, 128 GB unified memory)
- Docker (for vLLM Nemotron Omni)
- Python 3.12 + uv
- Node.js 20+ (for frontend)

### 1. Environment

```bash
cp .env.example .env
# Edit .env and set:
#   ELEVENLABS_API_KEY=...
#   VLLM_MULTIMODAL=1
```

### 2. Start vLLM Nemotron Omni

```bash
bash scripts/start_vllm_backend.sh
```

This starts Nemotron-3-Nano-Omni on GPU with optimized settings:
- `max_model_len=8192` (reduced from 16384 to save VRAM)
- `max_num_seqs=2`
- GPU utilization: ~39 GB

### 3. Start Backend API

```bash
cd features/delivery/disruptron-api
uv run python disruptron_api/main.py
```

Backend serves on port **8010** with endpoints:
- `POST /v1/chat/stream` — chat with the agent (SSE streaming)
- `POST /v1/livefeed/cameras/{id}/analyze` — single-frame object detection
- `POST /v1/livefeed/cameras/{id}/stream` — temporal video stream analysis
- `GET /v1/livefeed/cameras` — list all TfL JamCams
- `GET /v1/geo/hazards` — GeoJSON hazard map data
- `POST /v1/geo/hazards/cluster` — GPU DBSCAN clustering (RAPIDS)

### 4. Start Frontend

```bash
cd features/delivery/web
npm install  # first time only
npx vite --host 0.0.0.0 --port 5175
```

Open http://localhost:5175 — the app has three main tabs:
- **Map** — Live hazard points, ward boundaries, route overlay
- **CCTV** — Camera grid + detail panel with "Analyze" button
- **Tactical Panel** — Real-time agent reasoning stream

### 5. Run 24/7 (autonomous)

```bash
./scripts/disruptron daemon
```

Or install as systemd user service:

```bash
./scripts/disruptron install
systemctl --user enable --now nv-disruptron.service
```

## LocateAnything-3B Setup

LocateAnything-3B is a 3B-parameter vision-language model with **Parallel Box Decoding (PBD)**. It runs alongside vLLM Nemotron on the same GPU.

The client (`features/vision/locate_anything_client.py`) uses:
- **bfloat16** dtype for best accuracy/memory balance
- **Chat-template API** via `processor.apply_chat_template()`
- **Hybrid generation mode** — starts with parallel block decoding, falls back to autoregressive when confidence drops
- **Temporal tracking** for video streams — IoU-based association with exponential moving average smoothing

### GPU Memory Budget

| Model | GPU Memory |
|-------|-----------|
| vLLM Nemotron | ~39 GB |
| LocateAnything-3B | ~8.5 GB |
| **Total** | **~48 GB / 128 GB** |

## Architecture

```
Frontend (React + Vite + MapLibre GL)
  ├── MapPage.tsx       — Route overlay + hazard points
  ├── CCTVPage.tsx      — Camera grid + LocateAnything analysis
  └── TacticalPanel     — SSE reasoning stream

Backend (FastAPI + uvicorn)
  ├── agent.py          — Nemotron Omni agent with live data injection
  ├── gateway.py        — REST endpoints
  ├── chat.py           — SSE streaming chat
  └── events.py         — Route SSE emitter

Vision Pipeline
  ├── locate_anything_client.py  — LocateAnything-3B + Nemotron fallback
  ├── hazard_pipeline.py         — 4-stage detect → parse → geotag → store
  ├── live_feed_pipeline.py      — TfL JamCam registry + snapshot fetch
  └── video_pipeline.py          — Video analysis (separate from CCTV)

GPU Layer (RAPIDS)
  ├── cudf_etl.py       — GPU-accelerated data processing
  ├── cuspatial_join.py — Spatial joins on hazard data
  ├── cugraph_network.py— Network analysis
  └── cuml_clustering.py— DBSCAN clustering

MCP Servers
  ├── transport/        — TfL journey planner + live disruption data
  ├── ops/              — System monitoring + alert triggers
  └── vision/           — Hazard taxonomy + detection pipeline
```

## Voice Mode

Pair OpenClaw mobile app → Talk Mode for hands-free voice interaction. The agent processes voice via ElevenLabs Scribe → Nemotron Omni multimodal reasoning.

Edit `features/agent/workspace/USER.md` with your EV/commute areas (kept private in voice output — no PII is ever sent to TTS).

## License

MIT — See LICENSE for details.
