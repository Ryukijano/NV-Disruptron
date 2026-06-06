#!/usr/bin/env bash
# Start Nemotron Omni on DGX Spark via vLLM OpenAI-compatible server (:8000)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/vllm-server.log"
PORT="${PORT:-8000}"
IMAGE="${VLLM_IMAGE:-vllm/vllm-openai:v0.20.0}"
MODEL="${VLLM_MODEL:-nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-NVFP4}"
SERVED_NAME="${VLLM_SERVED_MODEL:-nemotron_3_nano_omni}"
HF_CACHE="${HF_HOME:-$HOME/.cache/huggingface}"
CONTAINER_NAME="${VLLM_CONTAINER_NAME:-vllm-nemotron-omni}"

mkdir -p "$LOG_DIR" "$HF_CACHE"

run_docker() {
  if groups | grep -qw docker; then
    docker "$@"
  elif command -v sg >/dev/null 2>&1; then
    sg docker -c "docker $*"
  else
    sudo docker "$@"
  fi
}

if curl -fsS "http://127.0.0.1:${PORT}/v1/models" >/dev/null 2>&1; then
  echo "vLLM already responding on http://127.0.0.1:${PORT}/v1"
  exit 0
fi

if pgrep -af "llama-server.*--port ${PORT}" >/dev/null 2>&1; then
  echo "Stopping llama-server on port ${PORT}..."
  pkill -f "llama-server.*--port ${PORT}" || true
  sleep 2
fi

run_docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

echo "Pulling ${IMAGE} (first run may take several minutes)..."
run_docker pull "$IMAGE"

echo "Starting vLLM container ${CONTAINER_NAME}..."
run_docker run -d \
  --name "$CONTAINER_NAME" \
  --gpus all \
  --ipc=host \
  --shm-size=16g \
  -p "${PORT}:8000" \
  -v "${HF_CACHE}:/root/.cache/huggingface" \
  -e HF_HOME=/root/.cache/huggingface \
  ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
  "$IMAGE" \
  "$MODEL" \
    --served-model-name "$SERVED_NAME" \
    --host 0.0.0.0 \
    --port 8000 \
    --trust-remote-code \
    --enforce-eager \
    --gpu-memory-utilization "${VLLM_GPU_UTIL:-0.35}" \
    --max-model-len "${VLLM_MAX_MODEL_LEN:-16384}" \
    --max-num-seqs "${VLLM_MAX_NUM_SEQS:-4}" \
    --moe-backend marlin \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_coder \
    --reasoning-parser nemotron_v3 \
  > "$LOG_FILE" 2>&1

echo "Container started. Logs: docker logs -f ${CONTAINER_NAME}"
echo "Also tailing startup log: ${LOG_FILE}"

for i in $(seq 1 120); do
  if curl -fsS "http://127.0.0.1:${PORT}/v1/models" >/dev/null 2>&1; then
    echo "vLLM ready: http://127.0.0.1:${PORT}/v1 (model: ${SERVED_NAME})"
    curl -fsS "http://127.0.0.1:${PORT}/v1/models" | python3 -m json.tool | head -20
    exit 0
  fi
  if ! run_docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    echo "Container exited early. Last logs:" >&2
    run_docker logs "$CONTAINER_NAME" 2>&1 | tail -40 >&2
    exit 1
  fi
  sleep 10
  echo "waiting for vLLM... (${i}/120)"
done

echo "Timed out waiting for vLLM." >&2
run_docker logs "$CONTAINER_NAME" 2>&1 | tail -50 >&2
exit 1
