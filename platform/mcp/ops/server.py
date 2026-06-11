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


TFL_BASE_URL = "https://api.tfl.gov.uk"


def _tfl_params(extra: dict[str, object] | None = None) -> dict[str, object]:
    """Build query parameters including existing TfL auth if configured."""
    import os

    params: dict[str, object] = {}
    key = os.getenv("TFL_APP_KEY", "").strip()
    app_id = os.getenv("TFL_APP_ID", "").strip()
    if key:
        params["app_key"] = key
    if app_id:
        params["app_id"] = app_id
    if extra:
        params.update(extra)
    return params


async def _geocode_location(location: str) -> str:
    """Try to resolve a location string to a TfL-friendly format.

    Returns postcode if valid, lat/lon if geocoded, or original string.
    """
    import httpx

    # 1) Try postcode.io for UK postcodes
    pc = location.replace(" ", "").upper()
    if len(pc) >= 5:
        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                resp = await client.get(f"https://api.postcodes.io/postcodes/{pc}")
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == 200:
                        lat = data["result"]["latitude"]
                        lon = data["result"]["longitude"]
                        return f"{lat},{lon}"
            except Exception:
                pass

    # 2) Try TfL StopPoint search for station names
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            resp = await client.get(
                f"{TFL_BASE_URL}/StopPoint/Search/{location.replace(' ', '%20')}",
                params=_tfl_params({"maxResults": 1}),
            )
            if resp.status_code == 200:
                data = resp.json()
                matches = data.get("matches", [])
                if matches and matches[0].get("lat") and matches[0].get("lon"):
                    return f"{matches[0]['lat']},{matches[0]['lon']}"
        except Exception:
            pass

    # 3) If already looks like lat,lon, use as-is
    if "," in location and all(c.isdigit() or c in ".,- " for c in location):
        return location.strip()

    # 4) Fallback: return original (TfL may still resolve it)
    return location


@mcp.tool()
async def get_transit_route(origin: str, destination: str, mode: str = "transit") -> dict:
    """TfL Journey Planner route between two London places (tube, bus, walking, cycling).

    Uses the free TfL Unified API — no Google Maps key required.
    Accepts postcodes (SW1A 1AA), station names (Victoria), or lat/lon (51.5,-0.1).
    """
    import httpx

    mode_map = {
        "transit": "tube,overground,dlr,bus,tram,river-bus",
        "driving": "bus",
        "walking": "walking",
        "bicycling": "cycle",
    }
    tfl_modes = mode_map.get(mode, mode)

    # Geocode both ends to avoid ambiguous 300 responses
    from_resolved = await _geocode_location(origin)
    to_resolved = await _geocode_location(destination)

    params = _tfl_params({
        "mode": tfl_modes,
        "journeyPreference": "leastwalking",
    })

    from_enc = from_resolved.replace(" ", "%20")
    to_enc = to_resolved.replace(" ", "%20")
    url = f"{TFL_BASE_URL}/Journey/JourneyResults/{from_enc}/to/{to_enc}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        if resp.status_code in (300, 301, 302, 307, 308):
            # Ambiguous location — try with generic London context
            return {
                "ok": False,
                "error": f"Ambiguous location. Try a postcode (e.g., SW1A 1AA) or station name.",
            }
        resp.raise_for_status()
        data = resp.json()

    journeys = data.get("journeys", [])
    if not journeys:
        return {
            "ok": False,
            "error": data.get("message", "No journeys found — check origin/destination spelling."),
        }

    best = journeys[0]
    legs = best.get("legs", [])
    steps = []
    for leg in legs:
        mode_name = leg.get("mode", {}).get("name", "unknown")
        instruction = leg.get("instruction", {}).get("summary", "")
        duration_min = leg.get("duration", 0)
        steps.append({
            "mode": mode_name,
            "instruction": instruction,
            "duration_min": duration_min,
            "from": leg.get("departurePoint", {}).get("commonName", ""),
            "to": leg.get("arrivalPoint", {}).get("commonName", ""),
        })

    return {
        "ok": True,
        "source": "tfl_journey_planner",
        "duration": best.get("duration", 0),
        "duration_text": f"{best.get('duration', 0)} min",
        "start": origin,
        "end": destination,
        "legs": len(steps),
        "steps": steps,
    }


@mcp.tool()
async def search_places_near(query: str, location: str = "London, UK", radius_m: int = 3000) -> dict:
    """Search TfL stations/stops and London POIs near a location.

    Uses TfL StopPoint search + postcodes.io — no Google Maps key required.
    Accepts query like 'charger', 'tube station', 'step-free', 'parking'.
    """
    import httpx

    loc_lat, loc_lon = None, None
    pc = location.replace(" ", "").upper()
    async with httpx.AsyncClient(timeout=10.0) as client:
        pc_resp = await client.get(f"https://api.postcodes.io/postcodes/{pc}")
        if pc_resp.status_code == 200:
            pc_data = pc_resp.json()
            if pc_data.get("status") == 200:
                loc_lat = pc_data["result"]["latitude"]
                loc_lon = pc_data["result"]["longitude"]

    if loc_lat is None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            sp_resp = await client.get(
                f"{TFL_BASE_URL}/StopPoint/Search/{location.replace(' ', '%20')}",
                params=_tfl_params({"maxResults": 1}),
            )
            if sp_resp.status_code == 200:
                sp_data = sp_resp.json()
                matches = sp_data.get("matches", [])
                if matches:
                    loc_lat = matches[0].get("lat")
                    loc_lon = matches[0].get("lon")

    if loc_lat is None:
        return {"ok": False, "error": f"Could not geocode location: {location}"}

    # Use TfL StopPoint search around lat/lon (most reliable open endpoint)
    params = _tfl_params({
        "lat": loc_lat,
        "lon": loc_lon,
        "radius": min(radius_m, 5000),
        "stopTypes": "NaptanMetroStation,NaptanRailStation,NaptanBusCoachStation,NaptanFerryPort",
    })
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{TFL_BASE_URL}/StopPoint", params=params)
        resp.raise_for_status()
        data = resp.json()

    results = []
    q = query.lower()
    for place in (data.get("stopPoints") or [])[:12]:
        name = (place.get("commonName") or "").lower()
        modes = [m for m in (place.get("modes") or [])]
        mode_names = [m.lower() for m in modes]
        # Filter by query keyword if provided
        if q not in name and q not in " ".join(mode_names) and query not in ("", "all", "*"):
            continue
        results.append({
            "name": place.get("commonName"),
            "type": "StopPoint",
            "lat": place.get("lat"),
            "lon": place.get("lon"),
            "modes": modes,
            "distance_m": place.get("distance"),
        })

    return {"ok": True, "source": "tfl_stoppoint", "count": len(results), "places": results}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
