#!/usr/bin/env bash
# Full LifeLine stack: vLLM + NemoClaw config + channels + gateway health.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

"$ROOT/scripts/start_vllm_backend.sh"
echo ""
"$ROOT/features/observability/scripts/monitor_lifeline.sh" || echo "Warning: monitor reported issues — continuing."
echo ""
"$ROOT/features/agent-autonomous/scripts/configure_nemoclaw_lifeline.sh"
"$ROOT/features/delivery/scripts/configure_channels_lifeline.sh"

if ! curl -fsS "http://127.0.0.1:18789/health" >/dev/null 2>&1; then
  echo "Starting OpenClaw gateway..."
  openclaw gateway start
fi

echo ""
echo "LifeLine stack ready."
echo "  TUI:      openclaw tui"
echo "  CLI:      $ROOT/scripts/start_lifeline.sh"
echo "  Telegram: set TELEGRAM_BOT_TOKEN then re-run configure_channels_lifeline.sh"
echo "  Test:     $ROOT/scripts/test_nemoclaw_lifeline.sh"
echo ""

if [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  openclaw channels status --probe 2>/dev/null || true
fi
