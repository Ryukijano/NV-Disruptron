# Building an Open-Source NVIDIA Software Suite Template on DGX Spark: NV-Disruptron

*By the NV-Disruptron Team | NVIDIA Hack for Impact London 2026*

---

## Introduction

What does it take to build a reproducible, open-source template that showcases the breadth of NVIDIA's software suite on a single DGX Spark workstation? In this post, we share how we transformed **NV-Disruptron** — our London mobility intelligence project — into a maximum-relevance NVIDIA stack reference implementation, running entirely on the DGX Spark GB10 (128 GB unified memory, aarch64, CUDA 13).

We explicitly **did not** reach for niche simulation libraries like Sionna or Mitsuba. Instead, we focused on the NVIDIA technologies that directly solve real-world public-sector AI challenges: vision, safety, routing, retrieval, voice, analytics, and agent orchestration.

---

## The Stack: 10 NVIDIA Technologies on One Machine

| Layer | Technology | What It Does in NV-Disruptron |
|-------|-----------|-------------------------------|
| **Vision** | **LocateAnything-3B** | Per-frame open-vocab detection on 200+ TfL CCTV cameras (cars, buses, pedestrians, flooding) |
| **Vision** | **Cosmos Reason 2** | Causal video reasoning over CCTV clips — "Why did the crowd form?" |
| **Vision** | **DALI** | GPU JPEG decode + resize for CCTV frames, replacing CPU PIL |
| **Safety** | **NeMo Guardrails** | Topic rails (mobility only), jailbreak detection, PII output masking |
| **Routing** | **cuOpt** | VRP solver for hazard-response crew dispatch from depots to live incidents |
| **RAG** | **NeMo Retriever + cuVS** | GPU vector search (RAPIDS CAGRA) over TfL accessibility guides |
| **Voice** | **Riva NIM (ASR + TTS)** | Local privacy-first voice — zero cloud audio exposure |
| **Agent** | **Nemotron 3 Nano Omni** | Multimodal agent reasoning (text, image, audio) via vLLM |
| **Analytics** | **RAPIDS** (cuDF, cuSpatial, cuGraph, cuML) | GPU ETL, spatial joins, network analysis, DBSCAN clustering |
| **Orchestration** | **NeMo Agent Toolkit (NAT)** | Multi-step workflows with profiling, fallback chains, GPU telemetry |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     DGX Spark GB10                          │
│  (128 GB unified memory | aarch64 | CUDA 13)                │
├─────────────────────────────────────────────────────────────┤
│  Vision Layer                                               │
│    LocateAnything-3B → Parallel Box Decoding (hybrid)      │
│    Cosmos Reason 2  → Causal video clip analysis           │
│    DALI             → GPU JPEG decode + resize             │
├─────────────────────────────────────────────────────────────┤
│  Agent + Safety Layer                                       │
│    Nemotron 3 Nano Omni → vLLM (text/image/audio)        │
│    NeMo Guardrails      → Topic / jailbreak / PII rails  │
│    NeMo Agent Toolkit   → Workflow orchestration + traces  │
├─────────────────────────────────────────────────────────────┤
│  Data + Routing Layer                                       │
│    RAPIDS (cuDF/cuSpatial/cuGraph/cuML) → GPU analytics    │
│    cuOpt VRP           → Crew dispatch optimization        │
│    cuVS CAGRA          → GPU vector search for RAG         │
├─────────────────────────────────────────────────────────────┤
│  Voice Layer                                                │
│    Riva NIM ASR → Local speech-to-text (privacy-safe)    │
│    Riva NIM TTS → PII-filtered text-to-speech            │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

### 1. Why Not Sionna or Mitsuba?

We made a deliberate choice to exclude NVIDIA Sionna (optical simulation) and Mitsuba (rendering). While powerful, they are domain-specific tools for physics simulation and graphics research — not directly applicable to real-time public-sector mobility intelligence. Our template prioritizes technologies that a city council or transport authority can deploy today.

### 2. GPU Memory Budget on DGX Spark

| Component | GPU Memory |
|-----------|-----------|
| vLLM Nemotron Omni | ~39 GB |
| LocateAnything-3B | ~8.5 GB |
| cuOpt (sparse, on-demand) | ~2 GB |
| RAPIDS (cuDF/cuML) | ~4 GB |
| Riva NIM (ASR + TTS) | ~3 GB |
| Cosmos Reason 2 (NIM or fallback) | ~0–12 GB |
| **Total headroom** | **~60 GB / 128 GB** |

Everything fits comfortably with room for concurrent workloads.

### 3. Fallback-First Design

Every GPU-accelerated component has a CPU fallback:
- **cuOpt** → greedy nearest-neighbour routing
- **cuVS CAGRA** → FAISS-CPU → brute-force cosine similarity
- **DALI** → PIL + CPU resize
- **Cosmos Reason 2** → Nemotron Omni on first frame
- **Riva NIM** → text-only response (no cloud TTS)

This ensures the system never breaks when a container is not running.

### 4. Privacy by Default

- **Riva NIM** runs locally — voice data never leaves the machine
- **NeMo Guardrails** strips PII (email, phone, NHS numbers) before TTS synthesis
- **USER.md** activity profiles are kept local; no PII is sent to ElevenLabs

---

## Code Walkthrough: Three Standout Integrations

### cuOpt: Vehicle Routing for Hazard Response

```python
from platform.shared.gpu.cuopt_routing import plan_hazard_response_routes

# Read live hazards from SQLite + known depots → cuOpt VRP
result = plan_hazard_response_routes(
    hazard_ids=[42, 43, 44],
    max_vehicles=3,
    vehicle_capacity=5,
)
# Returns ordered waypoints per vehicle with total distance
```

Different from NeMo-Ray's set-cover mast placement: our cuOpt use is **live vehicle routing** from CCTV-detected hazards to nearest response depots (LFB, council depots).

### cuVS: GPU Vector Search for RAG

```python
from platform.shared.gpu.rag_engine import RAGEngine

rag = RAGEngine(embedding_dim=768)
rag.add_documents([
    {"text": "TfL Step-Free Access Guide...", "source": "tfl.gov.uk"},
])
results = rag.query("Where can I find step-free tube stations?")
# Uses cuVS CAGRA on GPU when available
```

### NeMo Guardrails: Agent Safety

```python
# config.yml defines topic rails + PII filters
# topics.co restricts queries to mobility/London only

# In chat.py, every user message is pre-screened:
gr_result = await guardrails.generate_async(
    messages=[{"role": "user", "content": user_text}]
)
if gr_result.get("bot_message"):
    return WebChatResponse(reply=gr_result["bot_message"], route="guardrails")
```

---

## Differentiation: Why NV-Disruptron Stands Apart

We looked closely at other NVIDIA hackathon winners (e.g., NeMo-Ray). Here's how we differentiate:

| Dimension | NeMo-Ray | NV-Disruptron |
|-----------|----------|---------------|
| **Domain** | Telecom mast placement | Public-sector mobility + accessibility |
| **Use of cuOpt** | Set-cover optimization | **Live VRP** for emergency crew dispatch |
| **Vision** | Static images | **Real-time CCTV streams** + temporal tracking |
| **Voice** | Cloud TTS | **Local Riva NIM** — privacy-first, zero cloud audio |
| **Safety** | — | **NeMo Guardrails** with topic/PII/jailbreak rails |
| **RAG** | — | **GPU vector search** (cuVS CAGRA) over accessibility docs |
| **Video Reasoning** | — | **Cosmos Reason 2** causal analysis over CCTV clips |
| **Agent Traces** | — | **NAT profiling** with GPU memory + latency per tool call |

---

## Reproducing on Your DGX Spark

```bash
git clone https://github.com/Smegalex/NV-Disruptron.git
cd NV-Disruptron
git checkout making-a-difference

# Install all NVIDIA suite dependencies
uv pip install -r requirements-nvidia-suite.txt

# Start vLLM Nemotron + embed endpoint
bash scripts/start_vllm_backend.sh
bash scripts/start_embed_backend.sh  # llama-nemotron-embed on :8001

# Start cuOpt server (optional, greedy fallback works without)
docker run -p 8080:8080 nvcr.io/nvidia/cuopt:24.12

# Start backend
uv run python features/delivery/disruptron-api/disruptron_api/main.py

# Start frontend
cd features/delivery/web && npm install && npx vite --host 0.0.0.0 --port 5175
```

---

## What's Next

- **Phase 2**: cuOpt server integration with live hazard DB sync
- **Phase 3**: Riva NIM container setup scripts for aarch64
- **Phase 4**: Cosmos Reason 2 NIM endpoint (when available)
- **Community**: PRs welcome for additional city adaptations (NYC, Singapore, Tokyo)

---

## Acknowledgements

Built for **NVIDIA Hack for Impact — London, June 2026**. Powered by the DGX Spark GB10 workstation and the full NVIDIA software suite.

---

*MIT License | [github.com/Smegalex/NV-Disruptron](https://github.com/Smegalex/NV-Disruptron)*
