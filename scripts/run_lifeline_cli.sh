#!/usr/bin/env bash
exec "$(cd "$(dirname "$0")/.." && pwd)/features/agent-interactive/scripts/run_lifeline_cli.sh" "$@"
