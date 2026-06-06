# Quick start

## Prerequisites

- Linux + CUDA, Docker, `uv`
- OpenClaw CLI (`npm install -g openclaw@latest`)

## Setup

```bash
cd /home/nvidia/NV-Disruptron-Gyana
cp .env.example .env   # set ELEVENLABS_API_KEY, optional TELEGRAM_BOT_TOKEN
make setup
./scripts/disruptron validate
```

## Run

```bash
# 24/7 autonomous monitor + voice alerts
./scripts/disruptron daemon

# Interactive chat (same stack, foreground)
./scripts/disruptron run
```

## Common variants

| Goal | Command |
|------|---------|
| Agent only (vLLM already up) | `disruptron run --no-vllm` |
| One-shot query | `disruptron query "How's London?"` |
| vLLM only | `disruptron vllm --recreate` |
| Health dashboard | `disruptron monitor` |
| Full stack + Telegram | `disruptron run --channels` |
| Skip AI-Q sidecar | `disruptron run --no-research` |

## Makefile aliases

`make start` → `disruptron run` · `make start-daemon` → `disruptron daemon` · `make validate` → `disruptron validate`

See [../scripts/README.md](../scripts/README.md) and [ENGINEERING.md](ENGINEERING.md).
