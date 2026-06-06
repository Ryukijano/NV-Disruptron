#!/usr/bin/env bash
# vLLM chat completion smoke test (implementation; repo root scripts/test_nemotron_backend.sh wraps this)
exec "$(cd "$(dirname "$0")" && pwd)/test/test_nemotron_backend.sh" "$@"
