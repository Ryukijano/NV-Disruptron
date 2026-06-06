#!/usr/bin/env bash
# Non-interactive LifeLine Grid smoke test via AI-Q + local vLLM + MCP tools
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

echo "==> vLLM health"
curl -fsS "${VLLM_BASE_URL:-http://127.0.0.1:8000/v1}/models" | python3 -m json.tool | head -25

echo
echo "==> AI-Q shallow research (MCP tools)"
"$ROOT/scripts/run_lifeline_query.sh" \
  "Use TfL and London impact tools only. What is the current Jubilee line status, which deprived wards along the route are most affected, and name the top ward?"

echo
echo "==> Casual London status query (tool-first prompt)"
"$ROOT/scripts/run_lifeline_query.sh" \
  "How's stuff in London rn? Use get_london_city_briefing or get_london_traffic_snapshot."

echo
echo "LifeLine Grid AI-Q test complete."
