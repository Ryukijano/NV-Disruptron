#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
uv sync --quiet 2>/dev/null || uv sync
exec uv run disruptron-api
