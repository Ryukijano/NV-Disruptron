#!/usr/bin/env bash
# Non-interactive LifeLine Grid smoke test via AI-Q + local vLLM + MCP tools
set -euo pipefail

AIQ_ROOT="${AIQ_ROOT:-/home/nvidia/aiq}"
CONFIG="${CONFIG:-/home/nvidia/NV-Disruptron/configs/config_lifeline_shallow_vllm.yml}"
VLLM_BASE_URL="${VLLM_BASE_URL:-http://127.0.0.1:8000/v1}"
export VLLM_SERVED_MODEL="${VLLM_SERVED_MODEL:-nemotron_3_nano_omni}"

echo "==> vLLM health"
curl -fsS "${VLLM_BASE_URL}/models" | python3 -m json.tool | head -25

echo
echo "==> AI-Q shallow research (MCP tools)"
cd "$AIQ_ROOT"
source .venv/bin/activate

dotenv -f deploy/.env run .venv/bin/nat run \
  --config_file "$CONFIG" \
  --input "Use TfL and London impact tools only. What is the current Jubilee line status, which deprived wards along the route are most affected, and name the top ward?"

echo
echo "LifeLine Grid AI-Q test complete."
