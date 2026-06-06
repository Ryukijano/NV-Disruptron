#!/usr/bin/env bash
# LifeLine Grid via NemoClaw/OpenClaw: vLLM + MCP config + interactive TUI
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
export VLLM_SERVED_MODEL="${VLLM_SERVED_MODEL:-nemotron_3_nano_omni}"
export NEMOCLAW_WORKSPACE="${NEMOCLAW_WORKSPACE:-$ROOT/nemoclaw/workspace}"

"$ROOT/scripts/start_vllm_backend.sh"

echo ""
"$ROOT/scripts/monitor_lifeline.sh" || echo "Warning: monitor reported issues — continuing anyway."
echo ""

"$ROOT/scripts/configure_nemoclaw_lifeline.sh"

# Ensure gateway is up for TUI / agent routing
if ! curl -fsS "http://127.0.0.1:18789/health" >/dev/null 2>&1; then
  echo "Starting OpenClaw gateway..."
  openclaw gateway start
fi

echo ""
echo "LifeLine NemoClaw ready. Try:"
echo "  openclaw agent --local --agent lifeline -m \"Monitor London and tell me what to investigate next\""
echo "  openclaw tui"
echo ""

exec openclaw tui
