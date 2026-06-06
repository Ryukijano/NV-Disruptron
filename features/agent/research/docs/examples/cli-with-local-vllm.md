# Example: CLI with local vLLM (NV-Disruptron)

```bash
make setup
./scripts/disruptron run
```

Phases inside `disruptron run`:

1. `disruptron vllm` — Nemotron on :8000  
2. `disruptron monitor` — smoke health  
3. `disruptron run` — AI-Q with `config_disruptron_cli.yml`

**vLLM already running:**

```bash
./scripts/disruptron run --no-vllm
./scripts/disruptron cli -v
```

Config: `configs/config_disruptron_cli.yml`  
Prompts: `features/agent/research/prompts/`
