"""Fetch live London briefing from disruptron_ops MCP modules."""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_IMPACT_MOD: ModuleType | None = None


def _load_impact() -> ModuleType:
    global _IMPACT_MOD  # noqa: PLW0603
    if _IMPACT_MOD is not None:
        return _IMPACT_MOD
    path = _REPO_ROOT / "platform" / "mcp" / "impact" / "server.py"
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    spec = importlib.util.spec_from_file_location("disruptron_impact_briefing", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _IMPACT_MOD = mod
    return mod


async def fetch_london_briefing() -> dict:
    """Return live briefing dict from impact MCP (Tube, roads, EV, equity)."""
    impact = _load_impact()
    return await impact.get_london_city_briefing()


def briefing_to_ui_blocks(briefing: dict) -> list[dict]:
    """Convert MCP briefing to AgentUi blocks for expressive surface."""
    snapshot = briefing.get("live_transport") or {}
    tube = snapshot.get("tube") or {}
    roads = snapshot.get("roads") or {}
    streets = snapshot.get("streets") or {}
    parking = briefing.get("parking_and_charging") or {}
    ev = parking.get("ev_charging") or snapshot.get("ev_charging") or {}

    metrics: list[dict] = [
        {
            "label": "Tube issues",
            "value": str(len(tube.get("lines_not_good_service") or [])),
            "tone": "down" if tube.get("lines_not_good_service") else "up",
        },
        {
            "label": "Congested roads",
            "value": str(roads.get("congested_corridor_count", 0)),
            "tone": "down" if (roads.get("congested_corridor_count") or 0) > 5 else "neutral",
        },
        {
            "label": "Street closures",
            "value": str(streets.get("closed_or_restricted_count", 0)),
            "tone": "neutral",
        },
    ]
    if ev:
        total = ev.get("total_connectors") or 0
        avail = ev.get("available") or 0
        ratio = f"{round(100 * avail / total)}%" if total else "—"
        metrics.append({"label": "EV available", "value": ratio, "tone": "up" if avail else "down"})

    status_items: list[dict] = []
    for line in (tube.get("lines") or [])[:8]:
        name = line.get("name") or line.get("id") or "?"
        status = (line.get("status") or "").lower()
        if "good" in status:
            tone = "good"
        elif "severe" in status or "closed" in status:
            tone = "severe"
        else:
            tone = "minor"
        status_items.append(
            {"line": name, "status": tone, "detail": line.get("reason") or line.get("status")}
        )

    blocks: list[dict] = [{"type": "metrics", "items": metrics}]
    if status_items:
        blocks.append({"type": "status-grid", "items": status_items})
    return blocks


def material_change(prev: dict | None, current: dict) -> tuple[bool, str | None]:
    """Threshold-based: return (changed, alert_title) if interesting."""
    if not prev:
        return False, None

    def _tube_count(b: dict) -> int:
        snap = b.get("live_transport") or {}
        return len((snap.get("tube") or {}).get("lines_not_good_service") or [])

    def _roads(b: dict) -> int:
        snap = b.get("live_transport") or {}
        return int((snap.get("roads") or {}).get("congested_corridor_count") or 0)

    def _streets(b: dict) -> int:
        snap = b.get("live_transport") or {}
        return int((snap.get("streets") or {}).get("closed_or_restricted_count") or 0)

    def _ev_ratio(b: dict) -> float:
        parking = b.get("parking_and_charging") or {}
        ev = parking.get("ev_charging") or {}
        total = ev.get("total_connectors") or 0
        avail = ev.get("available") or 0
        return avail / total if total else 1.0

    tube_delta = _tube_count(current) - _tube_count(prev)
    roads_delta = _roads(current) - _roads(prev)
    streets_delta = _streets(current) - _streets(prev)
    ev_drop = _ev_ratio(prev) - _ev_ratio(current)

    if tube_delta >= 2:
        return True, f"Tube: { _tube_count(current)} lines disrupted (+{tube_delta})"
    if roads_delta >= 3:
        return True, f"Road congestion spike (+{roads_delta} corridors)"
    if streets_delta >= 5:
        return True, f"Street closures increased (+{streets_delta})"
    if ev_drop >= 0.10:
        return True, "EV availability dropped >10% citywide"
    if _tube_count(current) >= 1 and tube_delta >= 1:
        lines = (current.get("live_transport") or {}).get("tube", {}).get("lines_not_good_service") or []
        if lines:
            first = lines[0].get("line") or "Line"
            return True, f"{first} — service disruption"
    return False, None
