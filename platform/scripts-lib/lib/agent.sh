# NV-Disruptron — OpenClaw 24/7 agent + AI-Q research + ElevenLabs alerts.

_disruptron_require_openclaw() {
  if ! command -v openclaw >/dev/null 2>&1; then
    echo "OpenClaw CLI not found — install: npm install -g openclaw@latest" >&2
    return 1
  fi
}

_disruptron_ensure_gateway() {
  if curl -fsS "http://127.0.0.1:18789/health" >/dev/null 2>&1; then
    return 0
  fi
  echo "Starting OpenClaw gateway..."
  openclaw gateway start
}

_disruptron_bootstrap() {
  local skip_vllm=0 skip_check=0 skip_research=0 with_channels=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --no-vllm) skip_vllm=1; shift ;;
      --no-check) skip_check=1; shift ;;
      --no-research) skip_research=1; shift ;;
      --channels) with_channels=1; shift ;;
      --) shift; break ;;
      *) break ;;
    esac
  done

  _disruptron_require_openclaw || return 1

  if [[ "$skip_vllm" -eq 0 ]]; then
    disruptron_cmd_vllm || return 1
    echo ""
  fi

  if [[ "$skip_research" -eq 0 ]]; then
    _disruptron_start_aiq_research || echo "Warning: deep research sidecar unavailable — live MCP mode only."
    echo ""
  fi

  if [[ "$skip_check" -eq 0 ]]; then
    disruptron_cmd_monitor || echo "Warning: monitor reported issues — continuing anyway."
    echo ""
  fi

  disruptron_cmd_configure ${with_channels:+--channels}

  _disruptron_ensure_gateway || return 1
}

disruptron_cmd_run() {
  local skip_vllm=0 skip_check=0 skip_research=0 with_channels=0 mode=tui
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --no-vllm) skip_vllm=1; shift ;;
      --no-check) skip_check=1; shift ;;
      --no-research) skip_research=1; shift ;;
      --channels) with_channels=1; shift ;;
      --agent) mode=agent; shift ;;
      -h|--help)
        cat <<EOF
Usage: disruptron run [options]

  Interactive NV-Disruptron (vLLM + gateway + TUI). Heartbeat runs 24/7 in background.

Options:
  --no-vllm       Skip vLLM start
  --no-research   Skip AI-Q sidecar
  --no-check      Skip health monitor
  --channels      Enable Telegram / messaging channels
  --agent         One-shot probe instead of TUI
EOF
        return 0
        ;;
      --) shift; break ;;
      *) break ;;
    esac
  done

  local bootstrap_args=()
  [[ "$skip_vllm" -eq 1 ]] && bootstrap_args+=(--no-vllm)
  [[ "$skip_check" -eq 1 ]] && bootstrap_args+=(--no-check)
  [[ "$skip_research" -eq 1 ]] && bootstrap_args+=(--no-research)
  [[ "$with_channels" -eq 1 ]] && bootstrap_args+=(--channels)
  _disruptron_bootstrap "${bootstrap_args[@]}" || return 1

  if [[ "$mode" == "agent" ]]; then
    exec openclaw agent --local --agent disruptron \
      -m "Monitor London live APIs. Alert me on transport or EV changes near the user."
  fi

  echo ""
  echo "NV-Disruptron ready — chat, voice (Talk Mode), or let daemon monitor 24/7."
  echo "  Control UI:  http://127.0.0.1:18789/"
  echo "  24/7 mode:   disruptron daemon"
  echo "  Voice TTS:   ElevenLabs ${ELEVENLABS_API_KEY:+enabled}${ELEVENLABS_API_KEY:-(set ELEVENLABS_API_KEY)}"
  echo ""
  exec openclaw tui
}

disruptron_cmd_query() {
  local query="${1:?Usage: disruptron query \"your question\"}"
  shift
  local skip_vllm=0 skip_check=0 skip_research=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --no-vllm) skip_vllm=1; shift ;;
      --no-check) skip_check=1; shift ;;
      --no-research) skip_research=1; shift ;;
      *) break ;;
    esac
  done
  local bootstrap_args=()
  [[ "$skip_vllm" -eq 1 ]] && bootstrap_args+=(--no-vllm)
  [[ "$skip_check" -eq 1 ]] && bootstrap_args+=(--no-check)
  [[ "$skip_research" -eq 1 ]] && bootstrap_args+=(--no-research)
  _disruptron_bootstrap "${bootstrap_args[@]}" || return 1
  exec openclaw agent --local --agent disruptron \
    --session-id "disruptron-query-$(date +%s)" --timeout 600 -m "$query"
}
