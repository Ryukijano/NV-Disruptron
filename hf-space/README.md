---
title: "Gyanateet's Portfolio"
emoji: "🚀"
colorFrom: "green"
colorTo: "blue"
sdk: "docker"
python_version: "3.11"
app_file: "start_space.py"
pinned: false
license: "mit"
---

# Gyanateet's Portfolio — Hugging Face Space Backend

This directory contains the backend that runs inside the Hugging Face Space `Ryukijano/gyanateet-portfolio`.

It runs a FastAPI backend (`/api/*`) on port `7860`, serving chat, TfL live data, and health endpoints.

## Services

| Service | Port | Purpose |
|---------|------|---------|
| Reverse proxy | `7860` | Routes `/api/*` to FastAPI and everything else to Streamlit |
| FastAPI | `8010` | NV-Disruptron API endpoints (chat, TfL, health) |
| vLLM | `8000` | Local Nemotron-3-Nano-4B model inference |
| Streamlit | `8501` | Existing CatCon portfolio (preserved) |

## Sync

This directory is synced to the Hugging Face Space automatically via the GitHub Actions workflow in `.github/workflows/sync-to-hf-space.yml`.

Trigger: push to `main` on `Ryukijano/NV-Disruptron` when `hf-space/**` changes.

## Local test

```bash
cd hf-space
python3 -m pip install -r disruptron/requirements.txt
python3 -m uvicorn disruptron.api:app --port 8010
```

## Files

- `Dockerfile` — Space container image
- `start_space.py` — Launcher for proxy + FastAPI + vLLM + Streamlit
- `runtime-requirements.txt` — Existing portfolio dependencies
- `disruptron/requirements.txt` — NV-Disruptron backend dependencies
- `disruptron/api.py` — FastAPI app
- `disruptron/agent.py` — Lightweight vLLM chat agent
- `disruptron/proxy.py` — ASGI reverse proxy
- `hf_space_metadata.yml` — HF Space card metadata
