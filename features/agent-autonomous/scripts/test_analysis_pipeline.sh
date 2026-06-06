#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
export PYTHONPATH="$ROOT/features/agent-autonomous/mcp:$ROOT/platform/shared:$ROOT"

cd "$ROOT/features/agent-autonomous/workspace"
chmod +x scripts/run_analysis_pipeline.sh
./scripts/run_analysis_pipeline.sh

test -f analysis/metrics/latest.json
test -f analysis/snapshots/latest.json
grep -q stress_score analysis/metrics/latest.json
grep -qi 'stress score' analysis/CONTEXT.md
echo "Analysis pipeline test passed."
