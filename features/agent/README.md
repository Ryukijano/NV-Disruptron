# agent — NV-Disruptron OpenClaw runtime

**Single agent feature** — 24/7 monitor, interactive TUI, voice, vision, browser automation, and optional AI-Q research.

MCP servers and delivery APIs live under [platform/](../../platform/) — not in this folder.

## Run

```bash
./scripts/disruptron daemon
./scripts/disruptron run
./scripts/disruptron query "…"
./scripts/disruptron vllm --recreate
```

## Layout

```
agent/
├── workspace/         # AGENTS.md, skills, USER.md, VOICE.md
├── research/          # optional AI-Q sidecar configs + prompts
└── docs/
```

Symlinks: `disruptron` → here · `configs` → `research/configs/`

MCP: [platform/mcp/ops/](../../platform/mcp/ops/) · Delivery: [platform/delivery/](../../platform/delivery/)

## Docs

- [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md)
- [workspace/skills/README.md](workspace/skills/README.md)
