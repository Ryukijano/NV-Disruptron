# DGX Spark setup notes (spark-1240)

Host-specific overrides for this machine.

## Port conflict

Port **8000** is used by Endo3D BFF (`pipeline/bff/server.py`). vLLM runs on **8008**:

```bash
# In .env
PORT=8008
VLLM_BASE_URL=http://127.0.0.1:8008/v1
VLLM_API_KEY=vllm-local
```

Always use `./scripts/disruptron vllm --recreate` (reads `.env`) or `disruptron query --no-vllm` when vLLM is already up.

## GPU memory

With Endo3D BFF stopped, full **256k** context works:

```bash
VLLM_MAX_MODEL_LEN=262144
VLLM_GPU_UTIL=0.85
VLLM_MAX_NUM_SEQS=1
```

## Stopped to free resources (2026-06-06)

| Process | Freed | Restart |
|---------|-------|---------|
| Endo3D BFF `:8000` | ~5.4 GB VRAM + swap | `conda run -n 3d_recon python -u ~/3d_reconstruction/pipeline/bff/server.py` |
| Firefox | ~6 GB swap | Reopen from app menu |
| Docker `goofy_leavitt` (mcp/fetch) | minor | `docker start goofy_leavitt` if needed |

## Node.js

NemoClaw requires **Node 22+**. Installer added nvm:

```bash
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 22
export PATH="$HOME/.local/bin:$PATH"
```

OpenClaw: `~/.nvm/versions/node/v22.22.3/bin/openclaw`

## NemoClaw onboarding (optional)

CLI installed; sandbox onboarding skipped (needs sudo for NVIDIA CDI):

```bash
sudo mkdir -p /etc/cdi
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
nemoclaw onboard
```

Host stack works without NemoClaw: OpenClaw gateway + vLLM on :8008.

## Running stack

```bash
cd /home/aimsgroupuol/AIMSgeneral/Gyanateet/nvidia_ai_hack/NV-Disruptron
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 22
export PATH="$HOME/.local/bin:$PATH"
set -a && source .env && set +a

./scripts/disruptron vllm --recreate          # Nemotron Omni NVFP4
openclaw gateway start                        # agent :18789
features/delivery/disruptron-api/start.sh     # web chat API :8010
features/delivery/web/start.sh                # React UI :5173
```

## Verify

```bash
curl -s http://127.0.0.1:8008/v1/models | head
curl -s http://127.0.0.1:8010/health
curl -s http://127.0.0.1:8010/v1/integrations | python3 -m json.tool
./scripts/disruptron query --no-vllm "How is London transport?"
```

## Latency & integrations (2026-06)

| Setting | Default | Effect |
|---------|---------|--------|
| `DISRUPTRON_AGENT_LOCAL=1` | on | `openclaw agent --local` — skips gateway hop (~5–15s saved) |
| `DISRUPTRON_CHAT_MODE=agent` | agent | Direct subprocess; no HTTP self-loop |
| `DISRUPTRON_BACKEND_TIMEOUT_S=180` | 180 | Agent turn cap |
| Web `/v1/chat/stream` | SSE | Live status while Nemotron + MCP run |

Morning digest scheduler runs at **08:00 Europe/London** when `DISRUPTRON_SCHEDULER_ENABLED=1`. Web Notifications + Summaries sync via SSE (`/v1/events/stream`).

## Telegram (choose one)

**Use OpenClaw gateway** for interactive Telegram + **disruptron-api** for push. See [TELEGRAM.md](./TELEGRAM.md).

Replace `TELEGRAM_BOT_TOKEN=0000000000:DEV_PLACEHOLDER_TOKEN` with a real BotFather token, then:

```bash
./scripts/disruptron configure --channels
openclaw gateway restart
```

## Google Calendar (optional)

```bash
cd ~/google-calendar-mcp && npm run auth && npm run build
./scripts/disruptron calendar start
./scripts/disruptron configure   # registers MCP with OpenClaw
```

Check: `curl -s http://127.0.0.1:8010/v1/integrations | python3 -m json.tool`
