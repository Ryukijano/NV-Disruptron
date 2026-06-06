# inference

Local **Nemotron** via vLLM Docker.

## Run

```bash
./scripts/disruptron vllm
./scripts/disruptron vllm --recreate    # multimodal audio/image
./scripts/disruptron vllm --llama       # GGUF fallback (no Docker)
```

Implementation: `platform/scripts-lib/lib/vllm.sh`

## Defaults

| Setting | Value |
|---------|-------|
| Endpoint | `http://127.0.0.1:8000/v1` |
| Served name | `nemotron_3_nano_omni` |
| Logs | `logs/vllm-server.log` |
