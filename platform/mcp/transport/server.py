"""
TfL London MCP Server

Exposes Transport for London Unified API capabilities to AI agents via MCP.
Focus: Line disruptions (GET /Line/Mode/{modes}/Disruption and per-line variants).

Setup:
  1. Copy .env.example to .env and add your TFL_APP_KEY
  2. uv sync
  3. TFL_APP_KEY=... uv run python server.py
     or: uv run mcp run server.py

Get a free TfL API key: https://api-portal.tfl.gov.uk/
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # repo root (shared symlink)

from shared.tfl_client import (  # noqa: E402
    fetch_ev_charge_summary,
    fetch_london_traffic_snapshot,
    fetch_parking_and_charging_snapshot,
)

# Load environment variables from .env if present
load_dotenv()

# Configuration
TFL_BASE_URL = "https://api.tfl.gov.uk"
TFL_APP_KEY = os.getenv("TFL_APP_KEY", "").strip()
# app_id is deprecated for most use cases but kept for compatibility
TFL_APP_ID = os.getenv("TFL_APP_ID", "").strip()

# Create the MCP server
mcp = FastMCP(
    "TfL London",
    instructions=(
        "Transport for London (TfL) Unified API — live public transport AND road traffic. "
        "Tube/Overground/DLR: use get_line_status, get_line_disruptions. "
        "Road traffic & street works: get_all_road_status (congestion), get_street_disruptions (closures), "
        "get_all_road_disruptions, get_road_status, get_road_disruptions. "
        "EV charging: get_parking_and_charging_snapshot, get_ev_charge_summary, get_ev_charge_connectors. "
        "Car parks: list_tfl_car_parks, get_car_park_detail, get_stop_car_parks (live bays often HTTP 500). "
        "Quick overview: get_london_traffic_snapshot (includes EV + car parks). "
        "Line IDs: victoria, jubilee, northern, elizabeth. Road IDs: a1, a2, a3, a406, inner ring."
    ),
)


def _today_utc_range() -> tuple[str, str]:
    """TfL Street/Disruption requires startDate + endDate query params."""
    today = datetime.now(UTC).date()
    return (
        f"{today.isoformat()}T00:00:00",
        f"{today.isoformat()}T23:59:59",
    )


def _road_path_ids(road_ids: str) -> str:
    """Encode comma-separated road IDs for URL paths (e.g. inner ring)."""
    return ",".join(quote(part.strip(), safe="") for part in road_ids.split(",") if part.strip())


def _slim_road_disruption(item: dict) -> dict:
    """Return agent-friendly road disruption fields."""
    geo = item.get("geography") or {}
    coords = geo.get("coordinates") if isinstance(geo, dict) else None
    return {
        "id": item.get("id"),
        "location": item.get("location"),
        "comments": item.get("comments"),
        "currentUpdate": item.get("currentUpdate"),
        "severity": item.get("severity"),
        "category": item.get("category"),
        "subCategory": item.get("subCategory"),
        "status": item.get("status"),
        "corridorIds": item.get("corridorIds"),
        "hasClosures": item.get("hasClosures"),
        "levelOfInterest": item.get("levelOfInterest"),
        "startDateTime": item.get("startDateTime"),
        "endDateTime": item.get("endDateTime"),
        "point": item.get("point"),
        "coordinates": coords,
    }


def _slim_street_disruption(item: dict) -> dict:
    """Street-segment disruption (closures, lane restrictions)."""
    return {
        "streetName": item.get("streetName"),
        "closure": item.get("closure"),
        "directions": item.get("directions"),
        "location": item.get("location"),
        "comments": item.get("comments"),
        "severity": item.get("severity"),
        "category": item.get("category"),
        "subCategory": item.get("subCategory"),
        "disruptionId": item.get("disruptionId"),
        "startLat": item.get("startLat"),
        "startLon": item.get("startLon"),
        "endLat": item.get("endLat"),
        "endLon": item.get("endLon"),
        "startDateTime": item.get("startDateTime"),
        "endDateTime": item.get("endDateTime"),
        "levelOfInterest": item.get("levelOfInterest"),
    }


def _slim_road_status(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "displayName": item.get("displayName"),
        "statusSeverity": item.get("statusSeverity"),
        "statusSeverityDescription": item.get("statusSeverityDescription"),
        "statusAggregationStartDate": item.get("statusAggregationStartDate"),
        "statusAggregationEndDate": item.get("statusAggregationEndDate"),
        "bounds": item.get("bounds"),
    }


def _is_congested(status: dict) -> bool:
    desc = (status.get("statusSeverityDescription") or "").lower()
    severity = (status.get("statusSeverity") or "").lower()
    return desc not in ("no exceptional delays",) and severity not in ("good", "")


def _build_params(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build query parameters including authentication."""
    params: dict[str, Any] = {}
    if TFL_APP_KEY:
        params["app_key"] = TFL_APP_KEY
    if TFL_APP_ID:
        params["app_id"] = TFL_APP_ID
    if extra:
        params.update(extra)
    return params


async def _tfl_get(path: str, params: dict[str, Any] | None = None) -> Any:
    """Make an authenticated GET request to the TfL Unified API."""
    url = f"{TFL_BASE_URL}{path}"
    query_params = _build_params(params)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=query_params)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def get_line_disruptions_by_mode(modes: str) -> list[dict]:
    """Get current disruptions for all lines of the given TfL mode(s).

    This implements the exact TfL API operation:
    GET /Line/Mode/{modes}/Disruption

    Use this when the user wants disruptions across a whole mode of transport.

    Args:
        modes: Comma-separated list of modes. Examples:
               - "tube"                  (London Underground)
               - "tube,overground"       (Tube + London Overground)
               - "elizabeth-line,dlr"    (Elizabeth line + DLR)
               - "bus"                   (London Buses)
               - "tram"                  (Trams)

    Common modes: tube, overground, elizabeth-line, dlr, tram, bus, river-bus.

    Returns:
        List of disruption objects. Each contains:
          - description: Human readable message
          - category: RealTime | PlannedWork | Information
          - closureText: partSuspended | plannedClosure | etc.
          - affectedRoutes, affectedStops, etc.
    """
    if not modes or not modes.strip():
        raise ValueError("modes is required (e.g. 'tube' or 'tube,overground')")

    path = f"/Line/Mode/{modes.strip()}/Disruption"
    return await _tfl_get(path)


@mcp.tool()
async def get_line_disruptions(line_ids: str) -> list[dict]:
    """Get disruptions for one or more specific TfL lines by ID.

    This is the best tool when the user asks about a *particular line*
    (e.g. "Victoria line", "Jubilee", "Northern line delays").

    Uses the endpoint: GET /Line/{ids}/Disruption

    Args:
        line_ids: Comma-separated line IDs. Examples:
                  - "victoria"
                  - "jubilee"
                  - "northern,central,piccadilly"
                  - "elizabeth"

    Popular line IDs:
      tube: bakerloo, central, circle, district, hammersmith-city,
            jubilee, metropolitan, northern, piccadilly, victoria,
            waterloo-city

      other: elizabeth, london-overground, dlr, tram

    Returns:
        List of disruption objects (same structure as get_line_disruptions_by_mode).
    """
    if not line_ids or not line_ids.strip():
        raise ValueError("line_ids is required (e.g. 'victoria' or 'jubilee,northern')")

    path = f"/Line/{line_ids.strip()}/Disruption"
    return await _tfl_get(path)


@mcp.tool()
async def list_line_modes() -> list[str]:
    """List all valid modes that can be used with the Line API (tube, bus, etc.).

    Useful for discovery before calling disruption tools.
    """
    data = await _tfl_get("/Line/Meta/Modes")
    # Return only the modeName values that are generally useful
    return [m["modeName"] for m in data if isinstance(m, dict) and "modeName" in m]


@mcp.tool()
async def get_lines_by_mode(modes: str = "tube") -> list[dict]:
    """Get the list of lines that operate on the given mode(s).

    Use this to discover exact line IDs (e.g. "victoria", "jubilee") for a mode.

    Args:
        modes: Comma-separated modes, default "tube".

    Returns:
        List of line objects with id, name, modeName, etc.
    """
    path = f"/Line/Mode/{modes.strip()}"
    return await _tfl_get(path)


@mcp.tool()
async def get_line_status_by_mode(modes: str) -> list[dict]:
    """Get current service status for all lines of the given mode(s).

    Implements GET /Line/Mode/{modes}/Status

    Args:
        modes: Comma-separated modes (e.g. 'tube', 'elizabeth-line', 'overground,dlr').
    """
    if not modes or not modes.strip():
        raise ValueError("modes is required (e.g. 'tube')")
    return await _tfl_get(f"/Line/Mode/{modes.strip()}/Status")


@mcp.tool()
async def get_line_status(line_ids: str) -> list[dict]:
    """Get service status for specific TfL lines.

    Implements GET /Line/{ids}/Status

    Args:
        line_ids: Comma-separated line IDs (e.g. 'jubilee', 'victoria,northern').
    """
    if not line_ids or not line_ids.strip():
        raise ValueError("line_ids is required")
    return await _tfl_get(f"/Line/{line_ids.strip()}/Status")


@mcp.tool()
async def search_stop_points(query: str, modes: str | None = None) -> list[dict]:
    """Search TfL stops/stations by name.

    Implements GET /StopPoint/Search/{query}

    Args:
        query: Station or stop name (e.g. 'King's Cross', 'Stratford').
        modes: Optional comma-separated modes filter (e.g. 'tube,bus').
    """
    if not query or not query.strip():
        raise ValueError("query is required")
    params = {"modes": modes} if modes else None
    return await _tfl_get(f"/StopPoint/Search/{query.strip()}", params)


@mcp.tool()
async def get_stop_arrivals(stop_id: str) -> list[dict]:
    """Get live arrival predictions at a TfL stop.

    Implements GET /StopPoint/{id}/Arrivals

    Args:
        stop_id: Naptan stop ID (from search_stop_points).
    """
    if not stop_id or not stop_id.strip():
        raise ValueError("stop_id is required")
    return await _tfl_get(f"/StopPoint/{stop_id.strip()}/Arrivals")


@mcp.tool()
async def get_bike_points(borough: str | None = None) -> list[dict]:
    """Get Santander Cycles dock availability across London.

    Implements GET /BikePoint (optionally filtered client-side by borough name).

    Args:
        borough: Optional borough name filter (e.g. 'Hackney').
    """
    docks = await _tfl_get("/BikePoint")
    if borough:
        b = borough.lower().strip()
        docks = [d for d in docks if b in (d.get("placeName") or "").lower()]
    return docks[:50] if not borough else docks


@mcp.tool()
async def plan_journey(
    from_location: str,
    to_location: str,
    modes: str = "tube,bus,walking",
) -> dict:
    """Plan a multimodal journey using live TfL data.

    Implements GET /Journey/JourneyResults/{from}/to/{to}

    Args:
        from_location: Origin as lat,lon (51.507,-0.128), postcode, or Naptan ID.
        to_location: Destination as lat,lon, postcode, or Naptan ID.
        modes: Comma-separated modes (default 'tube,bus,walking').
    """
    if not from_location or not to_location:
        raise ValueError("from_location and to_location are required")
    path = f"/Journey/JourneyResults/{from_location.strip()}/to/{to_location.strip()}"
    params = {
        "useRealTimeLiveArrivals": "true",
        "mode": modes,
    }
    return await _tfl_get(path, params)


@mcp.tool()
async def list_tfl_roads() -> list[dict]:
    """List TfL-managed road corridors (A-roads, ring roads) for traffic queries.

    Implements GET /Road

    Returns road id and display name (e.g. a1, a406, inner ring).
    """
    roads = await _tfl_get("/Road")
    return [
        {"id": r.get("id"), "displayName": r.get("displayName")}
        for r in roads
        if isinstance(r, dict)
    ]


@mcp.tool()
async def get_all_road_status(congested_only: bool = False) -> dict:
    """Get live congestion status for all TfL-managed road corridors.

    Implements GET /Road/all/Status (all 24 corridors in one call).

    Args:
        congested_only: If True, return only corridors not on 'No Exceptional Delays'.
    """
    data = await _tfl_get("/Road/all/Status")
    statuses = [_slim_road_status(r) for r in data]
    if congested_only:
        statuses = [s for s in statuses if _is_congested(s)]

    return {
        "total_corridors": len(data),
        "congested_count": sum(1 for s in [_slim_road_status(r) for r in data] if _is_congested(s)),
        "corridors": statuses,
    }


@mcp.tool()
async def get_road_status(road_ids: str) -> list[dict]:
    """Get live congestion/status for specific TfL-managed roads.

    Implements GET /Road/{ids}/Status

    Args:
        road_ids: Comma-separated road IDs (e.g. 'a1,a2,a406', 'inner ring').
    """
    if not road_ids or not road_ids.strip():
        raise ValueError("road_ids is required (e.g. 'a1,a2,a406')")
    path_ids = _road_path_ids(road_ids)
    data = await _tfl_get(f"/Road/{path_ids}/Status")
    return [_slim_road_status(r) for r in data]


@mcp.tool()
async def get_road_disruptions(road_ids: str) -> list[dict]:
    """Get active road works, closures, and incidents on specific roads.

    Implements GET /Road/{ids}/Disruption

    Args:
        road_ids: Comma-separated road IDs (e.g. 'a1,a2', 'inner ring').
    """
    if not road_ids or not road_ids.strip():
        raise ValueError("road_ids is required")
    path_ids = _road_path_ids(road_ids)
    data = await _tfl_get(f"/Road/{path_ids}/Disruption")
    return [_slim_road_disruption(r) for r in data]


@mcp.tool()
async def get_street_disruptions(
    limit: int = 25,
    category: str | None = None,
    severity: str | None = None,
    borough_hint: str | None = None,
    closed_only: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Get disrupted street segments (closures, lane restrictions) across London.

    Implements GET /Road/all/Street/Disruption — requires startDate + endDate
    (defaults to today UTC if omitted).

    Args:
        limit: Max street segments to return (default 25).
        category: Optional filter (e.g. 'Works', 'Traffic Incidents').
        severity: Optional filter (e.g. 'Serious', 'Moderate', 'Minimal').
        borough_hint: Optional text filter on location (e.g. 'Tower Hamlets').
        closed_only: If True, only streets with closure != 'Open'.
        start_date: ISO date/datetime start (default: today 00:00 UTC).
        end_date: ISO date/datetime end (default: today 23:59 UTC).
    """
    if not start_date or not end_date:
        default_start, default_end = _today_utc_range()
        start_date = start_date or default_start
        end_date = end_date or default_end

    data = await _tfl_get(
        "/Road/all/Street/Disruption",
        {"startDate": start_date, "endDate": end_date},
    )

    filtered: list[dict] = []
    for item in data:
        if category and (item.get("category") or "").lower() != category.lower():
            continue
        if severity and (item.get("severity") or "").lower() != severity.lower():
            continue
        if borough_hint and borough_hint.lower() not in (item.get("location") or "").lower():
            continue
        if closed_only and (item.get("closure") or "").lower() in ("open", ""):
            continue
        filtered.append(_slim_street_disruption(item))

    return {
        "date_range": {"startDate": start_date, "endDate": end_date},
        "total_active": len(data),
        "returned": min(limit, len(filtered)),
        "streets": filtered[: max(1, limit)],
    }


@mcp.tool()
async def get_road_disruption_categories() -> list[str]:
    """List valid road/street disruption categories from TfL metadata.

    Implements GET /Road/Meta/Categories
    """
    return await _tfl_get("/Road/Meta/Categories")


@mcp.tool()
async def get_road_disruption_severities() -> list[dict]:
    """List valid road disruption severity levels from TfL metadata.

    Implements GET /Road/Meta/Severities
    """
    data = await _tfl_get("/Road/Meta/Severities")
    return [
        {
            "severityLevel": s.get("severityLevel"),
            "description": s.get("description"),
        }
        for s in data
        if isinstance(s, dict)
    ]


@mcp.tool()
async def get_all_road_disruptions(
    limit: int = 25,
    category: str | None = None,
    severity: str | None = None,
    borough_hint: str | None = None,
) -> dict:
    """Get all active road disruptions across London (street works, incidents, closures).

    Implements GET /Road/all/Disruption — primary tool for live road traffic impact.

    Args:
        limit: Max disruptions to return (default 25).
        category: Optional filter (e.g. 'Works', 'Collisions', 'Network delays').
        severity: Optional filter (e.g. 'Minimal', 'Moderate', 'Serious').
        borough_hint: Optional text filter on location (e.g. 'Islington', 'Westminster').
    """
    data = await _tfl_get("/Road/all/Disruption")
    filtered: list[dict] = []
    for item in data:
        if category and (item.get("category") or "").lower() != category.lower():
            continue
        if severity and (item.get("severity") or "").lower() != severity.lower():
            continue
        if borough_hint and borough_hint.lower() not in (item.get("location") or "").lower():
            continue
        filtered.append(_slim_road_disruption(item))

    return {
        "total_active": len(data),
        "returned": min(limit, len(filtered)),
        "disruptions": filtered[: max(1, limit)],
    }


@mcp.tool()
async def get_london_traffic_snapshot() -> dict:
    """One-call London transport, road traffic, EV charging, and car park overview.

    Combines: Tube, roads, streets, live EV connectors, car park directory.
    """
    return await fetch_london_traffic_snapshot()


@mcp.tool()
async def get_air_quality() -> dict:
    """Get current London air quality forecast from TfL.

    Implements GET /AirQuality
    """
    data = await _tfl_get("/AirQuality")
    current = None
    for entry in data.get("currentForecast") or []:
        if entry.get("forecastType") == "Current":
            current = entry
            break
    if not current and data.get("currentForecast"):
        current = data["currentForecast"][0]

    if not current:
        return {"status": "unavailable"}

    return {
        "forecastBand": current.get("forecastBand"),
        "forecastSummary": current.get("forecastSummary"),
        "nO2Band": current.get("nO2Band"),
        "o3Band": current.get("o3Band"),
        "pM10Band": current.get("pM10Band"),
        "pM25Band": current.get("pM25Band"),
        "fromDate": current.get("fromDate"),
        "toDate": current.get("toDate"),
    }


@mcp.tool()
async def get_mode_arrivals(mode: str = "tube", limit: int = 20) -> list[dict]:
    """Get live arrivals across an entire transport mode.

    Implements GET /Mode/{mode}/Arrivals

    Args:
        mode: Transport mode (tube, bus, dlr, overground, tram, elizabeth-line).
        limit: Max arrivals to return (default 20).
    """
    if not mode or not mode.strip():
        raise ValueError("mode is required")
    data = await _tfl_get(f"/Mode/{mode.strip()}/Arrivals")
    slim = []
    for arr in data[: max(1, limit)]:
        slim.append(
            {
                "stationName": arr.get("stationName"),
                "destinationName": arr.get("destinationName"),
                "lineName": arr.get("lineName"),
                "timeToStation": arr.get("timeToStation"),
                "expectedArrival": arr.get("expectedArrival"),
                "towards": arr.get("towards"),
                "modeName": arr.get("modeName"),
            }
        )
    return slim


def _place_props(place: dict) -> dict[str, str]:
    return {
        ap.get("key"): ap.get("value")
        for ap in place.get("additionalProperties") or []
        if ap.get("key") and ap.get("value") is not None
    }


def _slim_car_park(place: dict) -> dict:
    props = _place_props(place)
    return {
        "id": place.get("id"),
        "name": place.get("commonName"),
        "lat": place.get("lat"),
        "lon": place.get("lon"),
        "distance_metres": place.get("distance"),
        "address": ", ".join(v for k, v in props.items() if k.startswith("Address") and v),
        "postcode": props.get("PostCode"),
        "spaces": props.get("NumberOfSpaces") or props.get("TotalSpaces") or props.get("Spaces"),
        "disabled_bays": props.get("NumberOfDisabledBays"),
        "opening_hours": props.get("OpeningHours"),
        "open": props.get("Open"),
        "station_atco_code": props.get("StationAtcoCode"),
        "smartParkingCode": props.get("SmartParkingLocationCode"),
        "daily_tariff_cash": props.get("StandardTariffsCashDaily"),
        "has_ev_charging": props.get("CarElectricalChargingPoints"),
    }


def _slim_charge_connector(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "sourceSystemPlaceId": item.get("sourceSystemPlaceId"),
        "status": item.get("status"),
    }


@mcp.tool()
async def get_parking_and_charging_snapshot() -> dict:
    """One-call live EV charging + TfL car park directory overview.

    EV connectors: live via GET /Occupancy/ChargeConnector.
    Car parks: static metadata via GET /Place/Type/CarPark (live bay occupancy API currently HTTP 500).
    """
    return await fetch_parking_and_charging_snapshot()


@mcp.tool()
async def get_ev_charge_summary() -> dict:
    """Live summary of TfL EV charge connector availability across London.

    Implements GET /Occupancy/ChargeConnector (~349 connectors live).
    """
    return await fetch_ev_charge_summary()


@mcp.tool()
async def get_ev_charge_connectors(
    status: str | None = None,
    limit: int = 25,
) -> dict:
    """Get live EV charge connector occupancy (available / charging / out of service).

    Implements GET /Occupancy/ChargeConnector and optional filter by status.

    Args:
        status: Optional filter: Available, Charging, OutOfService, Unknown.
        limit: Max connectors to return (default 25).
    """
    data = await _tfl_get("/Occupancy/ChargeConnector")
    if status:
        data = [c for c in data if (c.get("status") or "").lower() == status.lower()]
    slim = [_slim_charge_connector(c) for c in data[: max(1, limit)]]
    return {
        "total_matching": len(data),
        "returned": len(slim),
        "connectors": slim,
    }


@mcp.tool()
async def get_ev_charge_connector(source_system_place_id: str) -> list[dict]:
    """Get live status for specific EV charge connector(s) by sourceSystemPlaceId.

    Implements GET /Occupancy/ChargeConnector/{ids}

    Args:
        source_system_place_id: e.g. 'ChargePointESB-UT06EL-3' (comma-separated for multiple).
    """
    if not source_system_place_id or not source_system_place_id.strip():
        raise ValueError("source_system_place_id is required")
    data = await _tfl_get(f"/Occupancy/ChargeConnector/{source_system_place_id.strip()}")
    if isinstance(data, dict):
        data = [data]
    return [_slim_charge_connector(c) for c in data]


@mcp.tool()
async def list_tfl_car_parks(limit: int = 25, name_hint: str | None = None) -> dict:
    """List TfL car parks with static metadata (name, address, capacity).

    Implements GET /Place/Type/CarPark (58 parks).

    Note: Live bay occupancy via GET /Occupancy/CarPark is currently returning HTTP 500
    from TfL — use this for locations/metadata only until that feed is restored.

    Args:
        limit: Max car parks to return.
        name_hint: Optional filter on car park name (e.g. 'Greenford').
    """
    places = await _tfl_get("/Place/Type/CarPark")
    if name_hint:
        hint = name_hint.lower()
        places = [p for p in places if hint in (p.get("commonName") or "").lower()]
    slim = [_slim_car_park(p) for p in places[: max(1, limit)]]
    return {
        "total_car_parks": len(places),
        "returned": len(slim),
        "live_occupancy_api_status": "unavailable (TfL /Occupancy/CarPark returns HTTP 500 as of 2026-06)",
        "car_parks": slim,
    }


@mcp.tool()
async def get_car_park_occupancy(car_park_id: str) -> dict:
    """Attempt live car park occupancy for a given TfL car park ID.

    Implements GET /Occupancy/CarPark/{id}

    Args:
        car_park_id: Place ID (e.g. 'CarParks_800444') or SmartParkingLocationCode.

    Note: TfL's occupancy feed frequently returns HTTP 500. On failure, returns
    static metadata from GET /Place/{id} when available.
    """
    if not car_park_id or not car_park_id.strip():
        raise ValueError("car_park_id is required")
    cid = car_park_id.strip()
    try:
        occ = await _tfl_get(f"/Occupancy/CarPark/{cid}")
        return {"car_park_id": cid, "occupancy": occ, "source": "live"}
    except httpx.HTTPStatusError as exc:
        place_id = cid if cid.startswith("CarParks_") else None
        fallback = None
        if place_id:
            try:
                fallback = _slim_car_park(await _tfl_get(f"/Place/{place_id}"))
            except httpx.HTTPStatusError:
                fallback = None
        return {
            "car_park_id": cid,
            "occupancy": None,
            "source": "unavailable",
            "tfl_error": exc.response.status_code,
            "message": "TfL /Occupancy/CarPark is currently failing — metadata only.",
            "metadata": fallback,
        }


@mcp.tool()
async def get_car_park_detail(car_park_id: str) -> dict:
    """Get full TfL car park metadata (capacity, tariffs, hours, station link).

    Implements GET /Place/{id} (e.g. CarParks_800444).

    Args:
        car_park_id: Place ID from list_tfl_car_parks or get_stop_car_parks.
    """
    if not car_park_id or not car_park_id.strip():
        raise ValueError("car_park_id is required")
    place = await _tfl_get(f"/Place/{car_park_id.strip()}")
    detail = _slim_car_park(place)
    detail["occupancy_live"] = None
    try:
        detail["occupancy_live"] = await _tfl_get(f"/Occupancy/CarPark/{car_park_id.strip()}")
        detail["occupancy_source"] = "live"
    except httpx.HTTPStatusError as exc:
        detail["occupancy_source"] = "unavailable"
        detail["occupancy_error"] = exc.response.status_code
    return detail


@mcp.tool()
async def get_stop_car_parks(stop_id: str, try_live_occupancy: bool = False) -> dict:
    """Get car parks linked to a TfL stop/station.

    Implements GET /StopPoint/{id}/CarParks

    Args:
        stop_id: Naptan ID (e.g. '940GZZLUGFD' for Greenford) — hub IDs may return empty.
        try_live_occupancy: If True, attempt GET /Occupancy/CarPark/{id} per park (often HTTP 500).
    """
    if not stop_id or not stop_id.strip():
        raise ValueError("stop_id is required")
    sid = stop_id.strip()
    parks = await _tfl_get(f"/StopPoint/{sid}/CarParks")
    results = []
    for park in parks:
        slim = _slim_car_park(park)
        if try_live_occupancy and park.get("id"):
            try:
                slim["occupancy_live"] = await _tfl_get(f"/Occupancy/CarPark/{park['id']}")
                slim["occupancy_source"] = "live"
            except httpx.HTTPStatusError as exc:
                slim["occupancy_source"] = "unavailable"
                slim["occupancy_error"] = exc.response.status_code
        results.append(slim)
    return {
        "stop_id": sid,
        "car_park_count": len(results),
        "car_parks": results,
        "hint": "Use Naptan ID (940GZZLUxxx) if hub ID returns empty.",
    }


@mcp.tool()
async def get_stop_crowding(stop_id: str, line_id: str) -> dict:
    """Get live crowding level at a stop for a given line.

    Implements GET /StopPoint/{id}/Crowding/{line}

    Args:
        stop_id: Naptan stop ID.
        line_id: Line ID (e.g. 'northern', 'central').
    """
    if not stop_id or not line_id:
        raise ValueError("stop_id and line_id are required")
    return await _tfl_get(f"/StopPoint/{stop_id.strip()}/Crowding/{line_id.strip()}")


@mcp.tool()
async def get_tfl_api_status() -> dict:
    """Quick health check + configuration info for this MCP server.

    Returns whether an app_key is configured and the base URL being used.
    Does not call the TfL API.
    """
    return {
        "server": "TfL London MCP Server",
        "tfl_base_url": TFL_BASE_URL,
        "app_key_configured": bool(TFL_APP_KEY),
        "app_key_preview": (TFL_APP_KEY[:6] + "..." + TFL_APP_KEY[-4:]) if TFL_APP_KEY else None,
        "note": "Without an app_key you are limited to ~50 requests/min (anonymous). "
                "Get a free key at https://api-portal.tfl.gov.uk/ (500 req/min product).",
    }


# Optional: expose a simple resource for the key status (some clients like resources)
@mcp.resource("tfl://config/status")
def tfl_config_status() -> dict:
    """Resource exposing current TfL MCP server configuration status."""
    return {
        "has_app_key": bool(TFL_APP_KEY),
        "base_url": TFL_BASE_URL,
    }


def main():
    """Entry point for running the server."""
    # Default transport is stdio, which is what most agent clients expect
    mcp.run()


if __name__ == "__main__":
    main()
