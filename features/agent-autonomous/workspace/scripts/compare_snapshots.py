#!/usr/bin/env python3
"""Diff two briefing snapshots — detect material changes for monitor feedback loop."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]


def _tube_lines(snap: dict) -> set[str]:
    b = snap.get("briefing") or snap
    lines = (b.get("live_transport") or {}).get("tube", {}).get("lines_not_good_service") or []
    return {x.get("line", "") for x in lines if x.get("line")}


def _road_congestion(snap: dict) -> int:
    b = snap.get("briefing") or snap
    return int((b.get("live_transport") or {}).get("roads", {}).get("congested_corridor_count", 0))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("older", type=Path)
    parser.add_argument("newer", type=Path, nargs="?", default=WORKSPACE / "analysis" / "snapshots" / "latest.json")
    args = parser.parse_args()

    old = json.loads(args.older.read_text(encoding="utf-8"))
    new = json.loads(args.newer.read_text(encoding="utf-8"))

    old_lines, new_lines = _tube_lines(old), _tube_lines(new)
    delta = {
        "tube_lines_added": sorted(new_lines - old_lines),
        "tube_lines_cleared": sorted(old_lines - new_lines),
        "congested_delta": _road_congestion(new) - _road_congestion(old),
        "material_change": bool(new_lines - old_lines or old_lines - new_lines or abs(_road_congestion(new) - _road_congestion(old)) >= 2),
    }

    out = WORKSPACE / "analysis" / "metrics" / "delta_latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(delta, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "delta": delta}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
