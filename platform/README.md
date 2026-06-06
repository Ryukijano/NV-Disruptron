# platform/

Shared infrastructure — MCP servers, delivery APIs, data prep, Python libs, and CLI modules.

```
platform/
├── mcp/                    # All MCP servers (see mcp/README.md)
│   ├── transport/          # TfL live data (~31 tools)
│   ├── spatial/            # Wards, IMD, geocoding
│   ├── impact/             # Briefing + equity scoring
│   └── ops/                # Slim disruptron_ops (9 tools, OpenClaw default)
├── delivery/               # Push + channel APIs
│   ├── outputs-api/
│   └── telegram/
├── data/
│   └── scripts/
│       └── prepare_wards.py
├── shared/                 # Python libs (tfl_client, disruptron_data, …)
└── scripts-lib/            # disruptron CLI modules (lib/*.sh)
```

## Quick paths

| What | Path |
|------|------|
| Slim MCP (default) | `platform/mcp/ops/` |
| Full TfL MCP | `platform/mcp/transport/` |
| Ward data prep | `platform/data/scripts/prepare_wards.py` |
| Push API | `platform/delivery/outputs-api/` |
| CLI logic | `platform/scripts-lib/lib/` |

Repo-root shortcut: `mcp/` → `platform/mcp/` (e.g. `mcp/spatial`, `mcp/impact`).
