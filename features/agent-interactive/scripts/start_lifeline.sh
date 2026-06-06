#!/usr/bin/env bash
# Full LifeLine AI-Q workflow (phases 1–4):
#   1. Inference  — start_vllm_backend.sh
#   2. Health     — monitor_lifeline.sh
#   3. CLI        — run_lifeline_cli.sh (config_lifeline_cli.yml)
# See features/agent-interactive/docs/examples/cli-with-local-vllm.md
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=../../../platform/scripts-lib/aiq_env.sh
source "$DIR/../../../platform/scripts-lib/aiq_env.sh"
# Optional: export TFL_APP_KEY=... for higher TfL rate limits

"$ROOT/scripts/start_vllm_backend.sh"

echo ""
"$ROOT/scripts/monitor_lifeline.sh" || echo "Warning: monitor reported issues — continuing anyway."
echo ""

exec "$ROOT/scripts/run_lifeline_cli.sh" "$@"
