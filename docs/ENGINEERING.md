# Engineering loop — NV-Disruptron

Standard workflow for **any** code change across the London mobility agent stack: MCP servers, OpenClaw agent, vLLM inference, delivery channels, observability, or documentation.

## 1. Frame the change

Identify the owning subsystem:

| Subsystem | Path |
|-----------|------|
| Agent runtime (OpenClaw, skills, heartbeat) | `features/agent/workspace/` |
| Slim ops MCP | `platform/mcp/ops/` |
| TfL transport MCP | `platform/mcp/transport/` |
| Spatial MCP | `platform/mcp/spatial/` |
| Impact MCP | `platform/mcp/impact/` |
| Agent configure / daemon | `platform/scripts-lib/lib/configure.sh`, `daemon.sh` |
| AI-Q research sidecar | `platform/scripts-lib/lib/research.sh` |
| Push API + Telegram channels | `platform/delivery/` |
| vLLM / Nemotron | `platform/scripts-lib/lib/vllm.sh` |
| Validate + monitor + tests | `platform/scripts-lib/lib/observability.sh`, `test.sh` |
| Shared Python + shell libs | `platform/shared/`, `platform/scripts-lib/` |
| Docs + Cursor rules | `docs/`, `.cursor/rules/` |

Decide whether the change is:

- **bug fix**
- **feature addition**
- **refactor**
- **performance work**
- **workflow/documentation only**

Prefer the smallest change that preserves the `./scripts/disruptron` CLI and MCP output contracts unless the user explicitly asks for a breaking change.

## 2. Inspect the contracts first

Before editing, confirm the relevant contract files and entry points:

- `Makefile` for standard local commands
- `scripts/disruptron` for CLI subcommands
- `platform/scripts-lib/env.sh` for paths and env defaults
- `docs/STRUCTURE.md` for repo layout
- The subsystem README or doc closest to the change

If the change touches the agent runtime, also inspect:

- `features/agent/workspace/AGENTS.md`, `HEARTBEAT.md`, `VOICE.md`, `USER.md`
- `platform/scripts-lib/lib/configure.sh`
- `platform/mcp/ops/server.py`
- `features/agent/workspace/skills/` (relevant `SKILL.md`)

If the change touches delivery, also inspect:

- `platform/delivery/outputs-api/disruptron_bot/gateway.py`
- `disruptron configure --channels` (in `lib/configure.sh`)
- `features/agent/docs/CHANNELS.md`

## 3. Implement in a narrow slice

- Change the authoritative module first; share logic via `platform/shared/` only.
- Keep MCP tool names, skill paths, and JSON response shapes stable unless the task requires otherwise.
- Preserve existing defaults; add env flags or feature gates before changing behavior.
- Add logging at the boundary of new behavior so failures are easy to localize.

## 4. Verify in layers

Run the narrowest useful checks first, then widen:

```bash
# Repository hygiene (after MCP dep changes)
make setup

# Fast gates — no LLM required
make validate
# or: ./scripts/disruptron validate

# Targeted unit / integration tests
make test
# or: ./scripts/disruptron test all
./scripts/disruptron test skills
./scripts/disruptron test analysis
./scripts/disruptron test transport
```

If the change touches a runtime path, add a smoke run:

```bash
# Inference
./scripts/disruptron vllm --recreate

# Interactive agent (vLLM already up)
./scripts/disruptron run --no-vllm

# One-shot query
./scripts/disruptron query "How's the Jubilee line?"

# 24/7 daemon
./scripts/disruptron daemon

# Channels
./scripts/disruptron run --channels
```

## 5. Compare against the contract

Check produced artifacts against expected layout:

- MCP briefing payloads (`summary`, tube/roads/EV fields)
- `features/agent/workspace/analysis/` metrics and `CONTEXT.md`
- OpenClaw agent id `disruptron`, MCP prefix `disruptron_ops__`
- ElevenLabs TTS follows `VOICE.md` (no PII in spoken output)
- outputs-api `/health` and push delivery counts
- Telegram bindings in `~/.openclaw/openclaw.json`

Do not merge a change that makes the output contract ambiguous.

## 6. Escalate only when necessary

- If a failure is isolated to one MCP server, test that package alone before broad changes.
- If a change affects multiple subsystems, split the work into separate commits or follow-up tasks.
- If a dependency is missing, keep the code path fallback-safe and document the blocker.

## Recommended companion docs

| Doc | Use when |
|-----|----------|
| [QUICKSTART.md](QUICKSTART.md) | First-time setup |
| [MCP.md](MCP.md) | Tool reference |
| [STRUCTURE.md](STRUCTURE.md) | Navigating the repo |
| [../features/agent/docs/DOCUMENTATION.md](../features/agent/docs/DOCUMENTATION.md) | Full agent index |
| [../features/agent/docs/CHANNELS.md](../features/agent/docs/CHANNELS.md) | Telegram + push API |
| [../.cursor/rules/engineering-loop.mdc](../.cursor/rules/engineering-loop.mdc) | Cursor agent rule (short form) |
