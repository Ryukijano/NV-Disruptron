# Development guide

See [ENGINEERING.md](ENGINEERING.md) for the full change workflow.

## Prerequisites

- Linux + CUDA (tested: DGX Spark aarch64)
- Docker (vLLM)
- `uv` (MCP servers)
- OpenClaw CLI + gateway
- AI-Q at `/home/nvidia/aiq` with `.venv` (optional)

## One-time setup

```bash
cd /home/nvidia/NV-Disruptron-Gyana
./scripts/disruptron setup
./scripts/disruptron validate
```

Manual MCP sync:

```bash
for d in platform/mcp/transport platform/mcp/spatial platform/mcp/impact platform/mcp/ops platform/delivery/outputs-api; do
  (cd "$d" && uv sync)
done
uv run python platform/data/scripts/prepare_wards.py
```

## Daily commands

| Command | Action |
|---------|--------|
| `make validate` | Full smoke (MCP + skills + analysis + outputs-api) |
| `make test` | Targeted test suites |
| `./scripts/disruptron daemon` | 24/7 monitor |
| `./scripts/disruptron run` | Interactive TUI |

## Adding an MCP tool

1. Implement in the appropriate `platform/mcp/<name>/server.py`
2. Reuse `platform/shared/` — do not duplicate logic
3. If needed for slim mode, re-export in `platform/mcp/ops/server.py`
4. Update `features/agent/workspace/TOOLS.md` and a skill if needed
5. `./scripts/disruptron validate`

## Repo layout

- **MCP servers** → `platform/mcp/` only
- **Agent runtime** → `features/agent/workspace/`
- **CLI** → `scripts/disruptron` → `platform/scripts-lib/lib/`

See [STRUCTURE.md](STRUCTURE.md) and [CONTEXT.md](CONTEXT.md) (token/compaction/memory strategy).
