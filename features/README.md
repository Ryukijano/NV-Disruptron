# Features

Product-facing capabilities. **Infrastructure** (MCP, delivery, data) lives in [platform/](../platform/).

## Layout

| Feature | Path | Role |
|---------|------|------|
| **agent** | `agent/` | OpenClaw workspace, skills, research sidecar, docs |
| **inference** | `inference/` | Pointer — use `./scripts/disruptron vllm` |
| **observability** | `observability/` | Pointer — logic in `platform/scripts-lib/lib/` |

## Platform (MCP + delivery)

| Component | Path |
|-----------|------|
| All MCP servers | [platform/mcp/](../platform/mcp/) |
| Push API + Telegram | [platform/delivery/](../platform/delivery/) |
| Ward data prep | [platform/data/scripts/](../platform/data/scripts/) |

## Run

```bash
./scripts/disruptron daemon    # 24/7 monitor
./scripts/disruptron run       # interactive
./scripts/disruptron setup     # sync MCPs + ward data
./scripts/disruptron validate
```

Docs: [docs/INDEX.md](../docs/INDEX.md) · [platform/README.md](../platform/README.md)
