#!/usr/bin/env bash
# Fallback: Nemotron Omni GGUF via llama.cpp on :8000 (no API keys)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
MODEL_DIR="${MODEL_DIR:-/home/nvidia/unsloth/NVIDIA-Nemotron-3-Nano-Omni-30B-A3B-Reasoning-GGUF}"
LLAMA_SERVER="${LLAMA_SERVER:-/home/nvidia/llama.cpp/build/bin/llama-server}"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/llama-server.log"
PORT="${PORT:-8000}"

mkdir -p "$LOG_DIR"

if [[ ! -x "$LLAMA_SERVER" ]]; then
  echo "llama-server not found at $LLAMA_SERVER" >&2
  exit 1
fi

if curl -fsS "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; then
  echo "Inference backend already running on http://127.0.0.1:$PORT/v1"
  exit 0
fi

api_key_args=()
if [[ -n "${NEMOTRON_API_KEY:-}" ]]; then
  api_key_args=(--api-key "$NEMOTRON_API_KEY")
fi

nohup "$LLAMA_SERVER" \
  -m "$MODEL_DIR/NVIDIA-Nemotron-3-Nano-Omni-30B-A3B-Reasoning-UD-Q4_K_XL.gguf" \
  --mmproj "$MODEL_DIR/mmproj-BF16.gguf" \
  --host 127.0.0.1 \
  --port "$PORT" \
  -ngl all \
  -c "${CTX_SIZE:-16384}" \
  -rea off \
  -a "nemotron_3_nano_omni,nvidia/nemotron-3-nano-omni-30b-a3b,unsloth/NVIDIA-Nemotron-3-Nano-Omni-30B-A3B-Reasoning-GGUF" \
  "${api_key_args[@]}" \
  > "$LOG_FILE" 2>&1 &

echo "Starting llama-server (PID $!) — log: $LOG_FILE"
for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; then
    echo "Ready: http://127.0.0.1:$PORT/v1"
    exit 0
  fi
  sleep 3
done

echo "Timed out. Tail log:" >&2
tail -30 "$LOG_FILE" >&2
exit 1
