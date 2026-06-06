# AI-Q deep-research sidecar (port 8001). vLLM must be on :8000 first.

_disruptron_aiq_port() {
  echo "${AIQ_SERVER_PORT:-8001}"
}

_disruptron_aiq_url() {
  echo "http://127.0.0.1:$(_disruptron_aiq_port)"
}

_disruptron_start_aiq_research() {
  local port url log_dir log_file pid_file aiq_root config
  port="$(_disruptron_aiq_port)"
  url="$(_disruptron_aiq_url)"
  aiq_root="${AIQ_ROOT:-/home/nvidia/aiq}"
  config="${DISRUPTRON_API_CONFIG:-$DISRUPTRON_ROOT/configs/config_disruptron_api.yml}"
  log_dir="$DISRUPTRON_ROOT/logs"
  log_file="$log_dir/aiq-research.log"
  pid_file="$log_dir/aiq-research.pid"

  mkdir -p "$log_dir"
  export AIQ_SERVER_URL="$url"
  export DISRUPTRON_ROOT

  if curl -fsS "${url}/health" >/dev/null 2>&1; then
    echo "AI-Q research API already up at ${url}"
    return 0
  fi

  if [[ ! -d "$aiq_root/.venv" ]]; then
    echo "Warning: AI-Q not found at $aiq_root — deep research sidecar skipped." >&2
    echo "  Install: cd $aiq_root && ./scripts/setup.sh" >&2
    return 0
  fi

  if [[ ! -f "$config" ]]; then
    echo "Warning: AI-Q config missing ($config) — deep research sidecar skipped." >&2
    return 0
  fi

  if ! curl -fsS "${VLLM_BASE_URL:-http://127.0.0.1:8000/v1}/models" >/dev/null 2>&1; then
    echo "Warning: vLLM not ready — start vLLM before AI-Q research sidecar." >&2
    return 0
  fi

  echo "Starting AI-Q research API on ${url} ..."
  # shellcheck disable=SC1091
  (
    cd "$aiq_root"
    source .venv/bin/activate
    export DISRUPTRON_ROOT AIQ_DEV_ENV=skill AIQ_ENABLE_DEBUG=false
    export DISRUPTRON_PROMPTS_DIR="${DISRUPTRON_PROMPTS_DIR:-$DISRUPTRON_ROOT/features/agent/research/prompts}"
    if [[ -f deploy/.env ]]; then
      set -a
      # shellcheck disable=SC1091
      source deploy/.env
      set +a
    fi
    exec nat serve --config_file "$config" --host 127.0.0.1 --port "$port"
  ) >>"$log_file" 2>&1 &

  echo $! >"$pid_file"

  local i
  for i in $(seq 1 60); do
    if curl -fsS "${url}/health" >/dev/null 2>&1; then
      echo "AI-Q research API ready: ${url} (logs: $log_file)"
      return 0
    fi
    sleep 2
    echo "  waiting for AI-Q research API... (${i}/60)"
  done

  echo "Timed out waiting for AI-Q research API. Last log lines:" >&2
  tail -20 "$log_file" >&2 || true
  return 1
}
