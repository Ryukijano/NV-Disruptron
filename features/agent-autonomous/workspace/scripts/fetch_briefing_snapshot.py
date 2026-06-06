#!/usr/bin/env python3
"""Fetch live briefing JSON and save to analysis/snapshots/ for downstream analysis."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
REPO = WORKSPACE.parents[2]  # workspace → agent-autonomous → features → repo
sys.path.insert(0, str(REPO / "features" / "agent-autonomous" / "mcp"))
sys.path.insert(0, str(REPO / "platform" / "shared"))

from server import get_london_city_briefing  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, help="Output path (default: analysis/snapshots/<ts>.json)")
    args = parser.parse_args()

    briefing = await get_london_city_briefing()
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    out = args.out or WORKSPACE / "analysis" / "snapshots" / f"{ts}.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "fetched_at": ts,
        "briefing": briefing,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    latest = WORKSPACE / "analysis" / "snapshots" / "latest.json"
    latest.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(json.dumps({"ok": True, "path": str(out), "summary": briefing.get("summary", "")[:200]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
