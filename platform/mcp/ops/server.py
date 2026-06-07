"""Slim NV-Disruptron ops MCP — live London APIs for 24/7 autonomous monitoring."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[3]  # platform/mcp/ops → repo root
if str(ROOT / "platform" / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "platform" / "shared"))


def _load_server_module(name: str, rel_path: str) -> ModuleType:
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_impact = _load_server_module("disruptron_impact_srv", "platform/mcp/impact/server.py")
_tfl = _load_server_module("disruptron_tfl_srv", "platform/mcp/transport/server.py")
_spatial = _load_server_module("disruptron_spatial_srv", "platform/mcp/spatial/server.py")

mcp = FastMCP("disruptron-ops")


@mcp.tool()
async def get_london_city_briefing() -> dict:
    """Start here: composite Tube + roads + streets + EV + car parks + equity on worst lines."""
    return await _impact.get_london_city_briefing()


@mcp.tool()
async def score_line_disruption_impact(line_id: str) -> dict:
    """IMD-weighted ward exposure for a disrupted Tube/rail line (e.g. piccadilly, district)."""
    return await _impact.score_line_disruption_impact(line_id)


@mcp.tool()
async def get_london_traffic_snapshot() -> dict:
    """Full live transport snapshot when briefing is not enough."""
    return await _tfl.get_london_traffic_snapshot()


@mcp.tool()
async def get_parking_and_charging_snapshot() -> dict:
    """Live EV connectors + TfL car park directory."""
    return await _tfl.get_parking_and_charging_snapshot()


@mcp.tool()
async def get_ev_charge_summary() -> dict:
    """EV connector availability counts across London."""
    return await _tfl.get_ev_charge_summary()


@mcp.tool()
async def get_all_road_status(congested_only: bool = False) -> dict:
    """Road corridor status; set congested_only=true after briefing shows congestion."""
    return await _tfl.get_all_road_status(congested_only=congested_only)


@mcp.tool()
async def get_street_disruptions(
    start_date: str | None = None,
    end_date: str | None = None,
    severity: str | None = None,
    limit: int = 25,
) -> dict:
    """Street closures and restrictions (dates optional; defaults to today window)."""
    return await _tfl.get_street_disruptions(
        start_date=start_date,
        end_date=end_date,
        severity=severity,
        limit=limit,
    )


@mcp.tool()
async def lookup_ward_by_postcode(postcode: str) -> dict:
    """Resolve a London postcode to ward + IMD deprivation profile."""
    return await _spatial.lookup_ward_by_postcode(postcode)


@mcp.tool()
def get_ward_profile(ward: str) -> dict:
    """Ward name or code → IMD rank, borough, population."""
    return _spatial.get_ward_profile(ward)


@mcp.tool()
async def get_disruptron_ops_health() -> dict:
    """Health check: briefing reachable, ward data loaded, policy constants."""
    from disruptron_agent_policy import (  # noqa: PLC0415
        MAX_AGENT_STEPS_PER_TURN,
        MAX_SAME_TOOL_CALLS_PER_TURN,
    )

    try:
        briefing = await _impact.get_london_city_briefing()
        briefing_ok = bool(briefing.get("summary"))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "stage": "briefing"}

    try:
        wards = _spatial.get_data_status()
    except Exception as exc:  # noqa: BLE001
        wards = {"error": str(exc)}

    return {
        "ok": briefing_ok,
        "briefing_preview": (briefing.get("summary") or "")[:200],
        "ward_data": wards,
        "policy": {
            "max_steps_per_turn": MAX_AGENT_STEPS_PER_TURN,
            "max_same_tool_calls": MAX_SAME_TOOL_CALLS_PER_TURN,
        },
        "tools_exposed": 14,
    }


@mcp.tool()
def recall_conversation_context(
    channel: str = "browser",
    chat_id: str = "main",
    max_chars: int = 2400,
) -> dict:
    """Load compact SQLite recall (messages, facts, compaction) for continuing a chat without blowing context."""
    from context_store import ContextStore  # noqa: PLC0415

    db = ROOT / "data" / "disruptron_context.db"
    return ContextStore(db).recall(channel=channel, external_chat_id=chat_id, max_chars=max_chars)


@mcp.tool()
def store_memory_fact(
    fact_text: str,
    fact_key: str | None = None,
    channel: str | None = None,
    chat_id: str | None = None,
    source_run_id: str | None = None,
) -> dict:
    """Persist a durable fact to SQLite for cross-session memory (London ops, user prefs without PII)."""
    from context_store import ContextStore, conversation_id  # noqa: PLC0415

    store = ContextStore(ROOT / "data" / "disruptron_context.db")
    cid = conversation_id(channel, chat_id) if channel and chat_id else None
    fid = store.add_fact(
        fact_text=fact_text,
        scope="conversation" if cid else "global",
        conversation_id=cid,
        fact_key=fact_key,
        source_run_id=source_run_id,
    )
    return {"ok": True, "fact_id": fid}


@mcp.tool()
async def get_transit_route(origin: str, destination: str, mode: str = "transit") -> dict:
    """Google Maps route between two London places (transit, driving, walking, bicycling).

    Requires GOOGLE_MAPS_API_KEY in environment. Use for commute and nearest-station queries.
    """
    import os

    import httpx

    key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        return {
            "ok": False,
            "error": "GOOGLE_MAPS_API_KEY not configured — add to .env",
        }
    params = {
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "key": key,
        "region": "uk",
    }
    url = "https://maps.googleapis.com/maps/api/directions/json"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
    if data.get("status") != "OK":
        return {"ok": False, "status": data.get("status"), "error": data.get("error_message")}
    route = (data.get("routes") or [{}])[0]
    leg = ((route.get("legs") or [{}])[0])
    return {
        "ok": True,
        "summary": route.get("summary"),
        "duration": leg.get("duration", {}).get("text"),
        "distance": leg.get("distance", {}).get("text"),
        "start": leg.get("start_address"),
        "end": leg.get("end_address"),
        "steps": [
            {
                "instruction": s.get("html_instructions", ""),
                "mode": s.get("travel_mode"),
                "duration": s.get("duration", {}).get("text"),
            }
            for s in (leg.get("steps") or [])[:12]
        ],
    }


@mcp.tool()
async def search_places_near(query: str, location: str = "London, UK", radius_m: int = 3000) -> dict:
    """Search Google Places near a London location (stations, chargers, POIs).

    Requires GOOGLE_MAPS_API_KEY in environment.
    """
    import os

    import httpx

    key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        return {"ok": False, "error": "GOOGLE_MAPS_API_KEY not configured"}
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": f"{query} near {location}", "key": key, "region": "uk"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
    results = []
    for place in (data.get("results") or [])[:8]:
        results.append(
            {
                "name": place.get("name"),
                "address": place.get("formatted_address"),
                "rating": place.get("rating"),
                "types": (place.get("types") or [])[:4],
            }
        )
    return {"ok": True, "count": len(results), "places": results}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
