# scripts/

**One CLI for everything:**

```bash
./scripts/disruptron <command>
```

## Commands

| Command | Purpose |
|---------|---------|
| `daemon` | 24/7 autonomous monitor + voice alerts |
| `run` | Interactive OpenClaw TUI |
| `query "…"` | One-shot agent query |
| `configure [--channels]` | Register MCP + OpenClaw + TTS |
| `vllm [--recreate] [--llama]` | Start Nemotron on `:8000` |
| `monitor [--watch] [--json]` | Health dashboard |
| `validate` | Full smoke test (no LLM) |
| `test [suite]` | Targeted tests: `all`, `skills`, `analysis`, `transport`, `agent` |
| `setup` | Sync MCP packages + ward data |
| `elevenlabs` | Configure ElevenLabs voice |
| `install` | systemd user service |

## Examples

```bash
./scripts/disruptron daemon
./scripts/disruptron run --channels
./scripts/disruptron test all
./scripts/disruptron validate
```

## Where the logic lives

All implementation is nested under `platform/scripts-lib/lib/` — **not** scattered feature scripts:

```text
scripts/disruptron              ← only entry point
platform/scripts-lib/
  env.sh
  lib/agent.sh                  ← run, query, bootstrap
  lib/daemon.sh                 ← daemon, install
  lib/configure.sh              ← MCP + OpenClaw + Telegram
  lib/vllm.sh                   ← Docker vLLM + llama fallback
  lib/observability.sh          ← monitor, validate
  lib/test.sh                   ← test suites
  lib/elevenlabs.sh
  lib/setup.sh
  lib/research.sh               ← AI-Q sidecar
```

Makefile aliases (`make validate`, `make test`, …) all delegate to `disruptron`.
