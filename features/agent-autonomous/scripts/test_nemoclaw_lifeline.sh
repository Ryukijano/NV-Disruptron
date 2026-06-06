#!/usr/bin/env bash
# Smoke test: NemoClaw local agent calls LifeLine MCP tools autonomously.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
export VLLM_SERVED_MODEL="${VLLM_SERVED_MODEL:-nemotron_3_nano_omni}"

"$ROOT/scripts/configure_nemoclaw_lifeline.sh"

if ! curl -fsS "http://127.0.0.1:8000/v1/models" >/dev/null 2>&1; then
  echo "ERROR: vLLM not reachable on :8000 — run start_vllm_backend.sh first" >&2
  exit 1
fi

PROMPT="${1:-Monitor London transport right now. Use live tools, then tell me the top 3 things to investigate next based on what you find.}"

echo "==> openclaw agent --local"
echo "Prompt: $PROMPT"
echo ""

SESSION_ID="lifeline-test-$(date +%s)"
openclaw agent --local --agent lifeline --session-id "$SESSION_ID" --timeout 300 -m "$PROMPT" 2>&1 | tee /tmp/nemoclaw_lifeline_test.log

if grep -qiE "isn't available|I need to stop retrying" /tmp/nemoclaw_lifeline_test.log; then
  echo ""
  echo "FAIL: agent gave up on MCP tools — inspect /tmp/nemoclaw_lifeline_test.log"
  exit 1
fi

if grep -qiE 'Tube:|congested|EV charging|disruption|Recommended|investigate|ward' /tmp/nemoclaw_lifeline_test.log; then
  echo ""
  echo "PASS: agent returned live London ops intelligence"
else
  echo ""
  echo "FAIL: response lacks live transport signals — inspect /tmp/nemoclaw_lifeline_test.log"
  exit 1
fi
