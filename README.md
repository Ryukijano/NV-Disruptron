# NV-Disruptron

**Autonomous London mobility intelligence** — NVIDIA Hack for Impact London 2026.

NV-Disruptron runs **24/7**, watches live TfL, EV charging, and CCTV feeds, and **proactively alerts** you by text and **ElevenLabs voice** when transport or charging conditions change for *your* mobility profile.

## Features

| Feature | Description | NVIDIA Tech |
|---------|-------------|-------------|
| **Dynamic Route Planning** | Ask "route me from X to Y" — fetches live TfL journey plans and streams route coordinates to the map | — |
| **CCTV Monitoring** | Browse 200+ TfL JamCams, click to analyze — or let the agent trigger **LocateAnything-3B** on-demand when your chat query matches a location/hazard | **LocateAnything-3B** |
| **Video Stream Analysis** | Temporal object tracking across sampled frames — filters out transient objects, keeps persistent detections | **LocateAnything-3B** |
| **GPU-Optimized Inference** | Both **LocateAnything-3B** and **Nemotron Omni** run on GPU simultaneously (~48 GB / 128 GB) | **vLLM** |
| **Parallel Box Decoding** | LocateAnything uses **hybrid PBD** — parallel block decoding for speed, AR fallback for accuracy | **LocateAnything-3B** |
| **RAPIDS GPU Analytics** | cuDF ETL, cuSpatial joins, cuGraph network analysis, cuML clustering on live hazard data | **RAPIDS** (cuDF, cuSpatial, cuGraph, cuML) |
| **GPU Vector Search RAG** | Ingest TfL guides + accessibility docs → query with GPU-accelerated retrieval (cuVS CAGRA) | **NeMo Retriever** + **cuVS** |
| **Hazard-Response Routing** | Plan optimal crew dispatch routes from depots to live hazards using VRP | **cuOpt** |
| **Causal Video Reasoning** | Upload CCTV clips for causal analysis: "Why did the crowd form?" | **Cosmos Reason 2** |
| **Privacy-First Voice** | Local ASR + TTS — zero cloud voice data exposure, PII stripped before speech | **Riva NIM** (ASR + TTS) |
| **Agent Safety** | Topic rails (mobility only), jailbreak detection, PII output masking | **NeMo Guardrails** |
| **Agent Orchestration** | Multi-step workflows with profiling, fallback chains, GPU telemetry | **NeMo Agent Toolkit (NAT)** |
| **24/7 Autonomous Monitor** | Proactive alerts via text + ElevenLabs voice when conditions change. Watcher loop + on-demand chat detection | — |
| **OpenClaw Agent** | Natural language chat with multimodal reasoning (text, image, audio) via Nemotron Omni | **Nemotron 3 Nano Omni** |

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
- `POST /v1/livefeed/cameras/{id}/analyze` — single-frame object detection (LocateAnything-3B)
- `POST /v1/livefeed/cameras/{id}/stream` — temporal video stream analysis
- `GET /v1/livefeed/cameras` — list all TfL JamCams
- `GET /v1/geo/hazards` — GeoJSON hazard map data
- `POST /v1/geo/hazards/cluster` — GPU DBSCAN clustering (RAPIDS cuML)
- `POST /v1/routing/hazard-response` — cuOpt VRP crew dispatch routes
- `GET /v1/routing/depots` — response depot locations
- `POST /v1/rag/query` — GPU vector search RAG query
- `POST /v1/rag/ingest` — ingest documents into RAG
- `GET /v1/rag/stats` — RAG index statistics
- `POST /v1/vision/cosmos-reason` — Cosmos Reason 2 video causal analysis
- `POST /v1/voice/transcribe` — Riva ASR (local privacy)
- `POST /v1/voice/synthesize` — Riva TTS (PII-safe)
- `GET /v1/voice/status` — Riva NIM health
- `POST /v1/agent/workflow` — NAT multi-step agent workflow
- `GET /v1/agent/traces` — agent profiling traces
- `GET /v1/agent/tools` — registered tools + fallback chains

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

## Hardware

NV-Disruptron was built and tested on the **NVIDIA DGX Spark** — a personal AI supercomputer powered by the **GB10 Grace Blackwell Superchip** with **128 GB of unified memory** and up to **1 petaFLOP of FP4 AI performance**.

The entire stack (vLLM Nemotron, LocateAnything-3B, RAPIDS GPU analytics, cuOpt routing, Riva voice) runs on a **single desktop box** with zero cloud dependency for inference.

| Component | DGX Spark Spec |
|-----------|---------------|
| GPU | NVIDIA GB10 Grace Blackwell |
| Unified Memory | 128 GB |
| AI Performance | Up to 1 petaFLOP (FP4) |
| NVMe SSD | 4 TB |
| OS | DGX OS (Ubuntu-based) |

Every GPU-accelerated module has a CPU fallback (pandas, geopandas, networkx, sklearn), so NV-Disruptron degrades gracefully on non-GPU hardware.

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

NVIDIA GPU Software Suite
  ├── Vision
  │   ├── locate_anything_client.py  — LocateAnything-3B (PBD hybrid mode)
  │   ├── cosmos_reason.py             — Cosmos Reason 2 video causal reasoning
  │   └── dali_pipeline.py             — DALI GPU JPEG decode for CCTV frames
  ├── Safety
  │   └── guardrails/                  — NeMo Guardrails (topic + jailbreak + PII)
  ├── Routing
  │   └── cuopt_routing.py             — cuOpt VRP for hazard-response crews
  ├── RAG
  │   └── rag_engine.py                — NeMo Retriever style (cuVS GPU vector search)
  ├── Voice
  │   └── riva_voice.py                — Riva NIM ASR + TTS (local, PII-safe)
  ├── Analytics
  │   ├── cudf_etl.py                  — GPU-accelerated data processing (RAPIDS)
  │   ├── cuspatial_join.py            — Spatial joins on hazard data
  │   ├── cugraph_network.py           — Network analysis
  │   └── cuml_clustering.py           — DBSCAN clustering
  └── Orchestration
      └── nat_orchestrator.py          — NeMo Agent Toolkit (workflows + profiling)

MCP Servers
  ├── transport/        — TfL journey planner + live disruption data
  ├── ops/              — System monitoring + alert triggers
  └── vision/           — Hazard taxonomy + detection pipeline
```

## Voice Mode

Pair OpenClaw mobile app → Talk Mode for hands-free voice interaction. The agent processes voice via ElevenLabs Scribe → Nemotron Omni multimodal reasoning.

Edit `features/agent/workspace/USER.md` with your EV/commute areas (kept private in voice output — no PII is ever sent to TTS).

## Community & Cloud Deployment

**GitHub Pages Frontend** — The optimistic-cyberpunk landing page + interactive map app is deployed at:

- https://ryukijano.github.io/NV-Disruptron/

**Hugging Face Space Backend** — A lightweight demo backend runs on the existing A10G Space using NVIDIA Nemotron-3-Nano-4B, fully local inference:

- https://huggingface.co/spaces/Ryukijano/CatCon-One-Shot-Controlnet-SD-1-5-b2
- API endpoint: `/api/*`

The HF Space backend is a smaller community demo; the full DGX Spark stack (LocateAnything-3B, RAPIDS, cuOpt, Riva, Cosmos Reason 2) remains on the local DGX Spark.

### How deployment works

1. Fork `Smegalex/NV-Disruptron` to `Ryukijano/NV-Disruptron`
2. Push to `main` triggers two GitHub Actions workflows:
   - `.github/workflows/deploy-gh-pages.yml` — builds the Vite frontend and deploys to GitHub Pages
   - `.github/workflows/sync-to-hf-space.yml` — syncs the `hf-space/` backend to the Hugging Face Space
3. Set GitHub repo secrets:
   - `HF_TOKEN` — Hugging Face write token
4. Enable GitHub Pages source: Settings → Pages → GitHub Actions

**Model Templates** — The repo includes swap-in templates for other small NVIDIA Nemotron models:
- `Nemotron-3-Nano-3B` — lightweight, faster inference
- `Nemotron-3-Nano-30B-A3B` — higher reasoning quality

Swap the model name in `scripts/start_vllm_backend.sh` and the `NEMOTRON_MODEL` env var. vLLM handles the rest.

**NVIDIA Developer Blog** — A deep-dive write-up on architecture, agent design, and how to adapt NV-Disruptron for other cities is in the works. Follow the repo for updates.

## License

MIT — See LICENSE for details.
