# Start Nemotron Omni via vLLM Docker (:8000). Idempotent if already healthy.

_disruptron_vllm_docker() {
  if groups | grep -qw docker; then
    docker "$@"
  elif command -v sg >/dev/null 2>&1; then
    sg docker -c "docker $*"
  else
    sudo docker "$@"
  fi
}

_disruptron_vllm_multimodal_enabled() {
  [[ "${VLLM_MULTIMODAL:-0}" == "1" ]]
}

_disruptron_vllm_container_has_multimodal() {
  local container="$1"
  _disruptron_vllm_docker inspect "$container" --format '{{join .Args " "}}' 2>/dev/null \
    | grep -q 'allowed-local-media-path'
}

# Nemotron Omni: max_position_embeddings 262144 (256k). GB10 default uses full window.
_disruptron_vllm_max_model_len() {
  echo "${VLLM_MAX_MODEL_LEN:-262144}"
}

_disruptron_vllm_gpu_util_for_len() {
  local max_len="$1"
  if [[ -n "${VLLM_GPU_UTIL:-}" ]]; then
    echo "$VLLM_GPU_UTIL"
    return
  fi
  if [[ "$max_len" -ge 262144 ]]; then
    echo "0.89"
  elif [[ "$max_len" -ge 131072 ]]; then
    echo "0.55"
  elif [[ "$max_len" -ge 65536 ]]; then
    echo "0.45"
  else
    echo "0.35"
  fi
}

_disruptron_vllm_max_num_seqs_for_len() {
  local max_len="$1"
  if [[ -n "${VLLM_MAX_NUM_SEQS:-}" ]]; then
    echo "$VLLM_MAX_NUM_SEQS"
    return
  fi
  if [[ "$max_len" -ge 262144 ]]; then
    echo "1"
  elif [[ "$max_len" -ge 131072 ]]; then
    echo "2"
  else
    echo "4"
  fi
}

_disruptron_vllm_container_max_model_len() {
  local container="$1"
  _disruptron_vllm_docker inspect "$container" --format '{{join .Args " "}}' 2>/dev/null \
    | sed -n 's/.*--max-model-len \([0-9]*\).*/\1/p' | head -1
}

disruptron_cmd_vllm() {
  local log_dir="$DISRUPTRON_ROOT/logs"
  local log_file="$log_dir/vllm-server.log"
  local port="${PORT:-8000}"
  local image="${VLLM_IMAGE:-vllm/vllm-openai:v0.20.0-aarch64-cu130-ubuntu2404}"
  local model="${VLLM_MODEL:-nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-NVFP4}"
  local served_name="${VLLM_SERVED_MODEL:-nemotron_3_nano_omni}"
  local hf_cache="${HF_HOME:-$HOME/.cache/huggingface}"
  local container_name="${VLLM_CONTAINER_NAME:-vllm-nemotron-omni}"
  local media_dir="${VLLM_MEDIA_DIR:-/tmp/disruptron-media}"
  local recreate=0 use_llama=0

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --recreate) recreate=1; shift ;;
      --llama) use_llama=1; shift ;;
      *) shift ;;
    esac
  done

  if [[ "$use_llama" -eq 1 ]]; then
    _disruptron_vllm_llama "$port" "$log_dir"
    return $?
  fi

  mkdir -p "$log_dir" "$hf_cache" "$media_dir"

  local max_model_len gpu_util max_num_seqs
  max_model_len="$(_disruptron_vllm_max_model_len)"
  gpu_util="$(_disruptron_vllm_gpu_util_for_len "$max_model_len")"
  max_num_seqs="$(_disruptron_vllm_max_num_seqs_for_len "$max_model_len")"

  if curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; then
    local running_len
    running_len="$(_disruptron_vllm_container_max_model_len "$container_name")"
    if _disruptron_vllm_multimodal_enabled \
      && ! _disruptron_vllm_container_has_multimodal "$container_name"; then
      echo "vLLM is running without multimodal flags — recreating for audio/image..."
      recreate=1
    elif [[ -n "$running_len" && "$running_len" != "$max_model_len" ]]; then
      echo "vLLM max-model-len ${running_len} != desired ${max_model_len} — recreating..."
      recreate=1
    elif [[ "$recreate" -eq 0 ]]; then
      echo "vLLM already responding on http://127.0.0.1:${port}/v1 (max-model-len: ${running_len:-unknown})"
      return 0
    fi
  fi

  if pgrep -af "llama-server.*--port ${port}" >/dev/null 2>&1; then
    echo "Stopping llama-server on port ${port}..."
    pkill -f "llama-server.*--port ${port}" || true
    sleep 2
  fi

  _disruptron_vllm_docker rm -f "$container_name" >/dev/null 2>&1 || true

  echo "Pulling ${image} (first run may take several minutes)..."
  _disruptron_vllm_docker pull "$image"

  local serve_args=(
    "$model"
    --served-model-name "$served_name"
    --host 0.0.0.0
    --port 8000
    --trust-remote-code
    --enforce-eager
    --gpu-memory-utilization "$gpu_util"
    --max-model-len "$max_model_len"
    --max-num-seqs "$max_num_seqs"
    --moe-backend marlin
    --enable-auto-tool-choice
    --tool-call-parser qwen3_coder
    --reasoning-parser nemotron_v3
  )

  if _disruptron_vllm_multimodal_enabled; then
    serve_args+=(--allowed-local-media-path /media)
    echo "Multimodal mode: audio + image input enabled (media dir: ${media_dir})"
  fi

  echo "Starting vLLM container ${container_name} (max-model-len=${max_model_len}, gpu-util=${gpu_util}, max-num-seqs=${max_num_seqs})..."
  if _disruptron_vllm_multimodal_enabled; then
    # Nemotron Omni audio requires vllm[audio] inside the container image.
    local serve_cmd
    serve_cmd=$(printf '%q ' vllm serve "${serve_args[@]}")
    _disruptron_vllm_docker run -d \
      --name "$container_name" \
      --gpus all \
      --ipc=host \
      --shm-size=16g \
      -p "${port}:8000" \
      -v "${hf_cache}:/root/.cache/huggingface" \
      -v "${media_dir}:/media" \
      -e HF_HOME=/root/.cache/huggingface \
      ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
      --entrypoint /bin/bash \
      "$image" \
      -lc "pip install -q 'vllm[audio]' && exec ${serve_cmd}" \
      > "$log_file" 2>&1
  else
    _disruptron_vllm_docker run -d \
      --name "$container_name" \
      --gpus all \
      --ipc=host \
      --shm-size=16g \
      -p "${port}:8000" \
      -v "${hf_cache}:/root/.cache/huggingface" \
      -e HF_HOME=/root/.cache/huggingface \
      ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
      "$image" \
      "${serve_args[@]}" \
      > "$log_file" 2>&1
  fi

  echo "Container started. Logs: docker logs -f ${container_name}"

  local i
  for i in $(seq 1 120); do
    if curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; then
      echo "vLLM ready: http://127.0.0.1:${port}/v1 (model: ${served_name}, max-model-len: ${max_model_len})"
      if _disruptron_vllm_multimodal_enabled; then
        echo "  modalities: text, image, audio (Nemotron Omni via vLLM)"
      fi
      return 0
    fi
    if ! _disruptron_vllm_docker ps --format '{{.Names}}' | grep -qx "$container_name"; then
      echo "Container exited early. Last logs:" >&2
      _disruptron_vllm_docker logs "$container_name" 2>&1 | tail -40 >&2
      return 1
    fi
    sleep 10
    echo "waiting for vLLM... (${i}/120)"
  done

  echo "Timed out waiting for vLLM." >&2
  _disruptron_vllm_docker logs "$container_name" 2>&1 | tail -50 >&2
  return 1
}

# GGUF fallback via llama.cpp when Docker vLLM is unavailable.
_disruptron_vllm_llama() {
  local port="${1:-8000}"
  local log_dir="${2:-$DISRUPTRON_ROOT/logs}"
  local model_dir="${MODEL_DIR:-/home/nvidia/unsloth/NVIDIA-Nemotron-3-Nano-Omni-30B-A3B-Reasoning-GGUF}"
  local llama_server="${LLAMA_SERVER:-/home/nvidia/llama.cpp/build/bin/llama-server}"
  local log_file="$log_dir/llama-server.log"

  mkdir -p "$log_dir"

  if [[ ! -x "$llama_server" ]]; then
    echo "llama-server not found at $llama_server" >&2
    return 1
  fi

  if curl -fsS "http://127.0.0.1:$port/v1/models" >/dev/null 2>&1; then
    echo "Inference backend already running on http://127.0.0.1:$port/v1"
    return 0
  fi

  local api_key_args=()
  [[ -n "${NEMOTRON_API_KEY:-}" ]] && api_key_args=(--api-key "$NEMOTRON_API_KEY")

  nohup "$llama_server" \
    -m "$model_dir/NVIDIA-Nemotron-3-Nano-Omni-30B-A3B-Reasoning-UD-Q4_K_XL.gguf" \
    --mmproj "$model_dir/mmproj-BF16.gguf" \
    --host 127.0.0.1 \
    --port "$port" \
    -ngl all \
    -c "${CTX_SIZE:-16384}" \
    -rea off \
    -a "nemotron-3-nano-omni,nemotron_3_nano_omni,nvidia/nemotron-3-nano-omni-30b-a3b,unsloth/NVIDIA-Nemotron-3-Nano-Omni-30B-A3B-Reasoning-GGUF" \
    "${api_key_args[@]}" \
    > "$log_file" 2>&1 &

  echo "Starting llama-server (PID $!) — log: $log_file"
  local _
  for _ in $(seq 1 40); do
    if curl -fsS "http://127.0.0.1:$port/v1/models" >/dev/null 2>&1; then
      echo "Ready: http://127.0.0.1:$port/v1"
      return 0
    fi
    sleep 3
  done

  echo "Timed out. Tail log:" >&2
  tail -30 "$log_file" >&2
  return 1
}
