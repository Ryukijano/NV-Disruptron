# NemoClaw + Nemotron Omni (DGX Spark)

[NVIDIA NemoClaw](https://docs.nvidia.com/nemoclaw/) wraps **OpenClaw** in an **OpenShell** sandbox and routes inference to local **Nemotron Omni** via host vLLM.

## Quick start

```bash
# One-shot: vLLM (256k) + OpenClaw profile + NemoClaw sandbox
./scripts/disruptron nemoclaw onboard

# Chat in browser (sandbox Control UI — port 18790 if 18789 is taken)
./scripts/disruptron nemoclaw url

# Status
./scripts/disruptron nemoclaw status

# Policy setup (NVIDIA Spark playbook — Telegram egress, etc.)
./scripts/disruptron nemoclaw policy-setup
# With public webhook (after TELEGRAM_BOT_TOKEN + cloudflared):
# ./scripts/disruptron nemoclaw policy-setup --install-cloudflared --tunnel
```

## Policy setup (Spark playbook)

Follows [NemoClaw Policy Setup](https://build.nvidia.com/spark/nemoclaw-applications/policy-setup):

```bash
export SANDBOX_NAME=disruptron
./scripts/disruptron nemoclaw policy-setup          # telegram egress + recover
openshell policy get disruptron --full | rg telegram   # verify api.telegram.org
```

| Step | Command |
|------|---------|
| Telegram network egress | `nemoclaw disruptron policy-add telegram -y` |
| Verify policy | `openshell policy get disruptron --full \| rg telegram` |
| Install cloudflared (aarch64 Spark) | `disruptron nemoclaw policy-setup --install-cloudflared` |
| Public webhook tunnel | `nemoclaw tunnel start` (after cloudflared + Telegram onboard) |

**Important:** `policy-add telegram` only opens egress to `api.telegram.org`. For a working Telegram bot you also need `TELEGRAM_BOT_TOKEN` in `.env` and a sandbox created with Telegram enabled at onboard (or `nemoclaw disruptron channels add telegram`).

```bash
# Host Disruptron Telegram (no NemoClaw tunnel) — alternative:
./scripts/disruptron configure --channels
```

## Two ways to chat

| Mode | URL | Use when |
|------|-----|----------|
| **NemoClaw sandbox** | `http://127.0.0.1:18790/` | Official secured stack (OpenShell policies, GPU in sandbox) |
| **Host Disruptron** | `http://127.0.0.1:18789/` | Hackathon MCP/skills workspace on host OpenClaw |

Both use the same host vLLM: `http://127.0.0.1:8000/v1` · model **`nemotron-3-nano-omni`** · **262144** context.

## Reasoning

Nemotron Omni is a **reasoning** model. Disruptron configure sets:

- `reasoning: true` on the vLLM model catalog entry
- `thinkingDefault: medium`
- `chat_template_kwargs.enable_thinking: true`

Model id **`nemotron-3-nano-omni`** (hyphenated) matches OpenClaw’s Nemotron vLLM plugin.

## Environment (`.env`)

```bash
VLLM_SERVED_MODEL=nemotron-3-nano-omni
VLLM_MAX_MODEL_LEN=262144
NEMOCLAW_REASONING=1
NEMOCLAW_PROVIDER=vllm          # when vLLM already on :8000
```

## Official install (if CLI missing)

```bash
curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
nemoclaw onboard
```

## Related

- [CONTEXT.md](CONTEXT.md) — 256k window tuning
- [DEVELOPMENT.md](DEVELOPMENT.md) — `./scripts/disruptron run` host stack
