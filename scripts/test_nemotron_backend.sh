#!/usr/bin/env bash
# Smoke test local inference backend (vLLM or llama.cpp) — no API keys required
set -euo pipefail

BASE_URL="${NEMOTRON_BASE_URL:-http://127.0.0.1:8000/v1}"
MODEL="${NEMOTRON_MODEL:-nemotron_3_nano_omni}"

curl_args=()
if [[ -n "${NEMOTRON_API_KEY:-}" ]]; then
  curl_args+=(-H "Authorization: Bearer ${NEMOTRON_API_KEY}")
fi

echo "==> GET $BASE_URL/models"
curl -fsS "${curl_args[@]}" "$BASE_URL/models" | python3 -m json.tool | head -40

echo
echo "==> POST $BASE_URL/chat/completions"
curl -fsS "${curl_args[@]}" "$BASE_URL/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$MODEL\",
    \"messages\": [
      {\"role\": \"system\", \"content\": \"You are LifeLine Grid.\"},
      {\"role\": \"user\", \"content\": \"One sentence: confirm you are running locally on DGX Spark.\"}
    ],
    \"max_tokens\": 80,
    \"temperature\": 0.2
  }" | python3 -c "
import json,sys
d=json.load(sys.stdin)
m=d['choices'][0]['message']
text=(m.get('content') or m.get('reasoning_content') or '').strip()
print('Response:', text)
"

echo
echo "Backend OK"
