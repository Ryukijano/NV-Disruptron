#!/usr/bin/env bash
# One-command LifeLine Grid launcher: vLLM backend + AI-Q CLI
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AIQ_ROOT="${AIQ_ROOT:-/home/nvidia/aiq}"
CONFIG="${CONFIG:-$ROOT/configs/config_urban_ops.yml}"

export VLLM_SERVED_MODEL="${VLLM_SERVED_MODEL:-nemotron_3_nano_omni}"
# Optional: export TFL_APP_KEY=... for higher TfL rate limits (anonymous access works without it)

"$ROOT/scripts/start_vllm_backend.sh"
cd "$AIQ_ROOT"
exec ./scripts/start_cli.sh --config_file "$CONFIG"
