#!/usr/bin/env bash
# Full feedback loop: snapshot → analyze → update CONTEXT.md
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$(cd "$DIR/.." && pwd)"
REPO="$(cd "$WORKSPACE/../../.." && pwd)"
export PYTHONPATH="$REPO/features/agent-autonomous/mcp:$REPO/platform/shared:$REPO${PYTHONPATH:+:$PYTHONPATH}"

cd "$WORKSPACE"
python3 scripts/fetch_briefing_snapshot.py
python3 scripts/analyze_transport.py
echo "Pipeline done. Read analysis/CONTEXT.md for next agent turn."
