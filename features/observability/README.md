# observability

Health checks and smoke tests — **no LLM required** for `validate`.

All logic lives in `platform/scripts-lib/lib/observability.sh` (invoked via `./scripts/disruptron`).

```bash
./scripts/disruptron validate
./scripts/disruptron monitor
./scripts/disruptron monitor --watch
./scripts/disruptron monitor --json
./scripts/disruptron test all
```

## What validate checks

- Ward CSV + shared Python imports
- TfL, spatial, impact MCP tools
- Agent workspace + skills
- Analysis feedback pipeline
- Disruptron ops MCP (slim)
- outputs-api pytest + calendar status
