#!/usr/bin/env python3
"""Sync OpenClaw browser/CLI sessions into disruptron_context.db."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "platform" / "shared"))

from context_store import ContextStore, sync_all_openclaw_sessions  # noqa: E402


def main() -> int:
    store = ContextStore(ROOT / "data" / "disruptron_context.db")
    result = sync_all_openclaw_sessions(store)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
