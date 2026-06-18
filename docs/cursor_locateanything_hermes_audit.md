# LocateAnything + Hermes audit
_Exported on 6/18/2026 at 22:03:37 GMT+1 from Cursor (3.7.40)_

---

**User**

The user wants to know if NV-Disruptron uses the LocateAnything model, wants it to work, and wants to connect "Hermes agent".

Work in: /home/aimsgroupuol/AIMSgeneral/Gyanateet/nvidia_ai_hack/NV-Disruptron

Tasks:
1. **LocateAnything audit** — Search codebase for locate_anything, LocateAnything, grounding, vision MCP. Read features/vision/locate_anything_client.py, hazard_pipeline.py, vision MCP server, .env.example, config. Determine: is it wired? enabled by default? what model/endpoint? what's broken or missing?

2. **Browser research** — Use web search or browser to find current info on:
   - LocateAnything-3B model (NVIDIA/HuggingFace) — how to deploy on DGX Spark / local inference
   - "Hermes agent" in NVIDIA/OpenClaw/agent context — could be Hermes-3 model, NVIDIA Hermes agent framework, or something in their stack. Search build.nvidia.com, GitHub, OpenClaw docs.

3. **Hermes connection** — Search the NV-Disruptron repo and parent AIMSgeneral workspace for any existing Hermes references. Determine what "connect Hermes agent" likely means and what integration points exist (OpenClaw, AI-Q, disruptron-api, MCP).

4. **Gap analysis** — What's needed to make LocateAnything work end-to-end? What's needed to connect Hermes?

5. Return a structured report:
   - Current LocateAnything status (implemented/partial/stub)
   - Exact files and env vars involved
   - Steps to make LocateAnything work on spark-1240
   - What Hermes agent is and how to connect it to NV-Disruptron
   - Recommended implementation plan (prioritized)

Read actual code — don't guess. Check if model weights are on disk, if services need starting, if there are TODOs or fallbacks to Nemotron only.

---

**Cursor**

Composer. Auditing NV-Disruptron for LocateAnything and Hermes integration — searching the codebase and gathering deployment docs in parallel.


Reading core implementation files and searching for OpenClaw/NemoClaw agent integration points.


# NV-Disruptron: LocateAnything + Hermes Audit Report

## Executive summary

| Component | Status |
|-----------|--------|
| **LocateAnything-3B** | **Partial** — architecture and call sites exist; runtime inference is broken; Nemotron fallback is the de facto path |
| **Vision MCP** | **Implemented but disconnected** — server exists; not registered with OpenClaw |
| **Hermes agent** | **Not integrated** — zero repo references; stack uses OpenClaw `disruptron` via NemoClaw optional sandbox |

---

## 1. LocateAnything current status: **PARTIAL**

### What is wired

LocateAnything is referenced across the vision stack:

| Layer | File | Role |
|-------|------|------|
| Client | `features/vision/locate_anything_client.py` | Primary LocateAnything-3B + Nemotron fallback |
| Image pipeline | `features/vision/hazard_pipeline.py` | Detect → parse → geotag → store |
| Video pipeline | `features/vision/video_pipeline.py` | Frame sampling → detect → temporal track |
| Vision MCP | `platform/mcp/vision/server.py` | 12 tools (`analyze_street_image_tool`, `analyze_video_tool`, etc.) |
| Gateway API | `features/delivery/disruptron-api/disruptron_api/gateway.py` | `POST /v1/hazard/upload`, `POST /v1/video/upload` |
| Health UI | `features/delivery/disruptron-api/disruptron_api/integrations.py` | `locateanything` block in `/v1/integrations` |
| Frontend | `features/delivery/web/src/components/layout/AppShell.tsx` | Green status if model cache exists |

### What is NOT wired

1. **Vision MCP is not registered with OpenClaw** — only `disruptron_ops` is registered (`configure.sh` slim mode). Agent cannot call `analyze_street_image_tool` etc.
2. **No dedicated vision venv/deps** — `disruptron-api` pyproject has no `torch`, `transformers`, `opencv-python-headless`, `decord`, or `lmdb`.
3. **Gateway import path broken** — `features/delivery/disruptron-api/start.sh` does not set `PYTHONPATH`; `from features.vision...` fails (`ModuleNotFoundError: No module named 'features'`).
4. **Health check is misleading** — `locateanything_status()` only checks HF cache dir exists, not whether the model loads or inference works.

### Enabled by default?

- **Code path**: yes — `get_client()` always tries LocateAnything first, then falls back to Nemotron (`fallback_to_nemotron=True`).
- **Actual behavior**: almost always Nemotron fallback, because LocateAnything load fails.

### Model / endpoint

| Setting | Value |
|---------|-------|
| Model ID | `nvidia/LocateAnything-3B` (hardcoded) |
| Local load | HuggingFace `transformers` in-process on `cuda` |
| Fallback | `NEMOTRON_URL` → `http://localhost:8008/v1` (vLLM Nemotron Omni) |
| External API | **Not implemented** — no `LOCATE_ANYTHING_URL` env var |

### Model weights on disk

**Yes — cached on spark-1240:**

```
~/.cache/huggingface/hub/models--nvidia--LocateAnything-3B  (7.3 GB)
```

Integrations API would report `status: "cached"`.

### What is broken (verified by runtime test)

Tested loading in `venv/cosmos3` (has `torch 2.11.0+cu130`, `transformers 4.57.6`):

```
LocateAnything-3B load failed: This modeling file requires the following packages 
that were not found in your environment: decord, lmdb. Run `pip install decord lmdb`
→ available: False
```

Additional bugs in `locate_anything_client.py`:

1. **Wrong model class** — uses `AutoModelForVision2Seq`; official NVIDIA README uses `AutoModel.from_pretrained(..., torch_dtype=torch.bfloat16)`.
2. **Missing `import torch`** — `_detect_locate_anything()` calls `torch.no_grad()` without importing torch.
3. **Wrong inference API** — uses generic `processor(images=..., text=...)` + `model.generate(**inputs)`; official recipe needs chat template, `image_grid_hws`, and `tokenizer=` passed to `generate()`.
4. **Heuristic bbox parser** — `_parse_box_text()` is marked as heuristic; may not match real output format.

### Fallback behavior

When LocateAnything is unavailable, `_detect_nemotron()` sends base64 image + JSON-detection prompt to Nemotron Omni at `NEMOTRON_URL/chat/completions` with `model: "nemotron-omni"`. vLLM on spark-1240 is healthy at `:8008` serving `nemotron-3-nano-omni`.

Live feed (`live_feed_pipeline.py`) and audio (`audio_pipeline.py`) use Nemotron Omni directly — not LocateAnything.

---

## 2. Browser research: LocateAnything-3B on DGX Spark

### Model facts ([HuggingFace nvidia/LocateAnything-3B](https://huggingface.co/nvidia/LocateAnything-3B))

- 3B VLM for open-vocab object detection, phrase grounding, OCR, UI element localization
- **Inference**: Transformers + BF16 + KV cache
- **Not supported**: vLLM, TensorRT-LLM, Triton (as of model card)
- **Requires**: `transformers==4.57.1` (v5 breaks), `trust_remote_code=True`
- **Recommended**: `LocateAnythingWorker` class from model card → wrap in FastAPI/gRPC

### DGX Spark deployment options

| Approach | Notes |
|----------|-------|
| **In-process Transformers** | Works on GB10 Blackwell; needs `decord`, `lmdb`, BF16 CUDA |
| **FastAPI sidecar** | [NVIDIA Developer Forums thread](https://forums.developer.nvidia.com/t/getting-nvidia-locateanything-3b-running-as-an-openai-compatible-api-on-a-dgx-spark-gb10-blackwell/371829) — `LocateAnythingWorker` in container, port 8889; not vLLM |
| **Docker UI** | [gammahazard/locate-anything](https://github.com/gammahazard/locate-anything) — `docker compose up`, ~12GB+ VRAM |

LocateAnything and Nemotron Omni can coexist: Nemotron on vLLM `:8008`, LocateAnything as separate Python/FastAPI service.

---

## 3. Hermes agent: what it is and repo status

### What "Hermes agent" means

**Not** the Hermes-3 LLM. In NVIDIA's current stack, **Hermes** = [Nous Research Hermes Agent](https://get-hermes.ai/) — a self-improving agent harness (skills + memory loop) that runs inside **NVIDIA NemoClaw** sandboxes alongside OpenClaw.

| Product | Role |
|---------|------|
| **OpenClaw** | Default agent harness (what NV-Disruptron uses) |
| **Hermes** | Alternative harness in NemoClaw — learns from experience, reuses workflows |
| **NemoClaw** | NVIDIA reference stack: OpenShell sandbox + policy + routed inference |
| **OpenShell** | Sandbox runtime, network policy, credential proxy |

Install Hermes mode:
```bash
export NEMOCLAW_AGENT=hermes
curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
# or post-install: nemohermes alias
```

Docs: [NemoClaw Hermes quickstart](https://docs.nvidia.com/nemoclaw/latest/get-started/quickstart-hermes.html), [NVIDIA blog on Hermes + NemoClaw](https://developer.nvidia.com/blog/deploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw/).

### Hermes references in NV-Disruptron / AIMSgeneral

**Zero Hermes references** in NV-Disruptron source. The stack is built around:

| Integration point | Current wiring |
|-------------------|----------------|
| Agent harness | **OpenClaw** (`openclaw` CLI installed) |
| Agent ID | `disruptron` (in `~/.openclaw/openclaw.json`) |
| MCP | `disruptron_ops` only (transport/impact/spatial slim bundle) |
| Chat engine | `disruptron_api/backend/agent.py` → `openclaw agent --local --agent disruptron` |
| NemoClaw | Optional via `./scripts/disruptron nemoclaw onboard` (still OpenClaw inside sandbox) |
| Workspace | `features/agent/workspace/` (skills, HEARTBEAT, ROUTING) |

`agent.py` error message mentions "NemoClaw / OpenClaw" but never Hermes.

### What "connect Hermes agent" likely means

1. **Replace or add** the agent harness from OpenClaw → Hermes via NemoClaw (`NEMOCLAW_AGENT=hermes`).
2. **Port NV-Disruptron workspace** (skills, USER.md, HEARTBEAT) into Hermes sandbox.
3. **Expose MCP tools** to Hermes (disruptron_ops + vision MCP) via OpenShell network policy.
4. **Optionally** point `disruptron-api` chat at Hermes instead of `openclaw agent`.

---

## 4. Gap analysis

### LocateAnything end-to-end gaps

| # | Gap | Impact |
|---|-----|--------|
| 1 | Missing Python deps (`torch`, `transformers`, `decord`, `lmdb`, `opencv-python-headless`) | Model never loads |
| 2 | Wrong `AutoModel` API + inference recipe | Would fail even with deps |
| 3 | Vision MCP not in `openclaw mcp list` | Agent cannot use hazard tools |
| 4 | Gateway missing `PYTHONPATH=$DISRUPTRON_ROOT` | `/v1/hazard/upload` import fails |
| 5 | No vision skill for agent | Agent uses Nemotron vision-browser, not LocateAnything |
| 6 | Health check = cache-only | UI shows green while inference is down |
| 7 | No dedicated venv for vision | Conflicts with vLLM GPU memory if loaded in same process |

### Hermes connection gaps

| # | Gap | Impact |
|---|-----|--------|
| 1 | No Hermes install/onboard path in repo | Manual NemoClaw setup only |
| 2 | `agent.py` hardcoded to `openclaw` subprocess | Web/Telegram chat won't use Hermes |
| 3 | Skills/workspace are OpenClaw format | Need Hermes-compatible port |
| 4 | MCP registration is OpenClaw-specific (`openclaw mcp set`) | Hermes needs separate tool wiring |
| 5 | NemoClaw sandbox GPU sharing with vLLM + LocateAnything | Memory planning needed on 128GB unified |

---

## 5. Steps to make LocateAnything work on spark-1240

### Option A — Fix in-process client (fastest for hackathon)

```bash
# 1. Create vision venv (separate from vLLM)
cd /home/aimsgroupuol/AIMSgeneral/Gyanateet/nvidia_ai_hack/NV-Disruptron
python3 -m venv venv/locateanything
source venv/locateanything/bin/activate
pip install "transformers==4.57.1" torch accelerate pillow httpx opencv-python-headless \
  lmdb einops timm scipy scikit-image
# decord: may need stub on aarch64 (see NVIDIA forum thread) or skip if optional

# 2. Verify model loads
python -c "
from transformers import AutoModel, AutoProcessor, AutoTokenizer
import torch
mid='nvidia/LocateAnything-3B'
tok=AutoTokenizer.from_pretrained(mid, trust_remote_code=True)
proc=AutoProcessor.from_pretrained(mid, trust_remote_code=True)
m=AutoModel.from_pretrained(mid, trust_remote_code=True, torch_dtype=torch.bfloat16).cuda().eval()
print('OK')
"

# 3. Fix locate_anything_client.py (AutoModel, chat template, image_grid_hws, import torch)

# 4. Register vision MCP
openclaw mcp set disruptron_vision "$(python3 -c "
import json; print(json.dumps({'command':'uv','args':['--directory','/home/aimsgroupuol/AIMSgeneral/Gyanateet/nvidia_ai_hack/NV-Disruptron/platform/mcp/vision','run','python','server.py']}))
")"

# 5. Fix gateway PYTHONPATH in start.sh:
# export PYTHONPATH="$DISRUPTRON_ROOT:$DISRUPTRON_ROOT/platform/shared"

# 6. Smoke test
python scripts/smoke_test_ws2_ws3.py
curl -F image=@data/samples/street.jpg http://127.0.0.1:8010/v1/hazard/upload
```

### Option B — FastAPI sidecar (production-friendly, avoids GPU contention)

Run `LocateAnythingWorker` as standalone service on `:8889` (per NVIDIA forum recipe). Add `LOCATE_ANYTHING_URL=http://127.0.0.1:8889` to client. Keeps Nemotron vLLM and LocateAnything isolated.

---

## 6. Steps to connect Hermes to NV-Disruptron

### Minimal path (parallel sandbox)

```bash
# 1. Install Hermes mode
export NEMOCLAW_AGENT=hermes
export NEMOCLAW_SANDBOX_NAME=disruptron-hermes
curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash

# 2. Point inference at host vLLM
export NEMOCLAW_PROVIDER=vllm
export NEMOCLAW_MODEL=nemotron-3-nano-omni
nemoclaw onboard --non-interactive -y

# 3. Add network policy for MCP + gateway
nemoclaw disruptron-hermes policy-add --from-file platform/nemoclaw/policies/google-calendar-mcp.yaml
# (create similar preset for host :8010, :8889 LocateAnything, TfL APIs)

# 4. Port workspace skills into Hermes sandbox
nemoclaw disruptron-hermes connect
# Copy features/agent/workspace/* → Hermes workspace

# 5. Register MCP inside Hermes sandbox (if supported) or HTTP-bridge tools
```

### Deeper integration (replace OpenClaw in disruptron-api)

1. Add `DISRUPTRON_AGENT_HARNESS=openclaw|hermes` env var.
2. In `agent.py`, branch: Hermes → HTTP to Hermes sandbox (`:8642/health`) or `nemoclaw exec`.
3. Keep `disruptron_ops` MCP available via OpenShell host bridge.
4. Add `disruptron-vision` skill pointing at vision MCP tools.

---

## 7. Recommended implementation plan (prioritized)

| Priority | Task | Effort | Unblocks |
|----------|------|--------|----------|
| **P0** | Fix `PYTHONPATH` in `disruptron-api/start.sh` | 5 min | Gateway hazard/video upload endpoints |
| **P0** | Create `venv/locateanything` + install deps (`transformers==4.57.1`, `lmdb`, torch) | 30 min | Model load |
| **P1** | Rewrite `locate_anything_client.py` to official `AutoModel` + `LocateAnythingWorker` recipe | 2–4 hrs | Real bounding boxes |
| **P1** | Register `disruptron_vision` MCP in `configure.sh` | 30 min | Agent can call hazard tools |
| **P1** | Fix `integrations.py` to call `client.is_available()` not just cache check | 15 min | Accurate UI status |
| **P2** | Add `disruptron-vision-hazards` OpenClaw skill | 1 hr | Agent knows when to use vision MCP |
| **P2** | FastAPI sidecar for LocateAnything (avoid vLLM VRAM clash) | 4 hrs | Stable 24/7 co-existence |
| **P3** | Hermes via `NEMOCLAW_AGENT=hermes` + policy presets for Disruptron services | 1 day | Self-improving agent harness |
| **P3** | `agent.py` harness abstraction (OpenClaw / Hermes) | 4 hrs | Unified web chat |

---

## Key files and env vars reference

### Files
```
features/vision/locate_anything_client.py   # client (needs fix)
features/vision/hazard_pipeline.py          # image pipeline
features/vision/video_pipeline.py           # video pipeline
platform/mcp/vision/server.py               # MCP server (not registered)
platform/scripts-lib/lib/configure.sh       # MCP registration (ops only)
features/delivery/disruptron-api/...        # gateway + integrations
features/agent/workspace/                   # OpenClaw agent (not Hermes)
platform/scripts-lib/lib/nemoclaw.sh        # NemoClaw integration (OpenClaw default)
```

### Env vars
```bash
NEMOTRON_URL=http://127.0.0.1:8008/v1          # fallback grounding
NEMOTRON_MODEL=nemotron-3-nano-omni
VLLM_BASE_URL=http://127.0.0.1:8008/v1
DISRUPTRON_AGENT_ID=disruptron
DISRUPTRON_AGENT_LOCAL=1
DISRUPTRON_SLIM_MCP=true                        # ops MCP only; no vision
HF_TOKEN=                                       # only if gated download
# Missing (should add):
# LOCATE_ANYTHING_URL=http://127.0.0.1:8889    # if sidecar
# LOCATE_ANYTHING_DEVICE=cuda
# DISRUPTRON_VISION_MCP=1
# NEMOCLAW_AGENT=hermes                          # for Hermes harness
```

---

**Bottom line:** NV-Disruptron **intends** to use LocateAnything-3B but **does not successfully run it today** — weights are on disk, code paths exist, but deps/API bugs and missing MCP registration mean Nemotron Omni grounding is the effective vision backend. Hermes is **not connected**; the live agent is OpenClaw `disruptron` with optional NemoClaw sandbox, and connecting Hermes requires NemoClaw Hermes mode plus MCP/workspace porting.

