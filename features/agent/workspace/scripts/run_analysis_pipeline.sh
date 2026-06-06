#!/usr/bin/env bash
# Full feedback loop: snapshot → analyze → update CONTEXT.md
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$(cd "$DIR/.." && pwd)"
REPO="$(cd "$WORKSPACE/../../.." && pwd)"

cd "$REPO/platform/mcp/ops"
uv run python "$WORKSPACE/scripts/fetch_briefing_snapshot.py"
uv run python "$WORKSPACE/scripts/analyze_transport.py"
echo "Pipeline done. Read analysis/CONTEXT.md for next agent turn."
