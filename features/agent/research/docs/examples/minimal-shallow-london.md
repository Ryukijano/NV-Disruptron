# Example: Minimal shallow London (NV-Disruptron)

```bash
./scripts/disruptron vllm
./scripts/disruptron query "How's London right now? Use get_london_city_briefing."
```

Config: `configs/config_disruptron_shallow_vllm.yml`  
Batch test: `features/agent/research/scripts/disruptron test agent`
