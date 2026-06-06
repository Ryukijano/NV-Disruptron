# agent/research — optional AI-Q deep research sidecar

Legacy AI-Q configs for long-form London research reports. **Not the default runtime** — NV-Disruptron uses OpenClaw + vLLM for interactive and autonomous modes.

## Start sidecar

```bash
./scripts/disruptron run          # starts sidecar automatically when available
# or skip: ./scripts/disruptron run --no-research
```

Config: `configs/config_disruptron_api.yml` (symlinked from repo root as `configs/`).

Port: `:8001` (`AIQ_SERVER_PORT`).

Skill: `disruptron-deep-research` in the agent workspace.
