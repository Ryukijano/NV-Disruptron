"""Shared TfL Unified API client for NV-Disruptron MCP servers."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

TFL_BASE_URL = "https://api.tfl.gov.uk"
TFL_APP_KEY = os.getenv("TFL_APP_KEY", "").strip()


def _build_params(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if TFL_APP_KEY:
        params["app_key"] = TFL_APP_KEY
    if extra:
        params.update(extra)
    return params


async def tfl_get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{TFL_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=_build_params(params))
        resp.raise_for_status()
        return resp.json()


def today_utc_range() -> tuple[str, str]:
    today = datetime.now(UTC).date()
    return f"{today.isoformat()}T00:00:00", f"{today.isoformat()}T23:59:59"


def road_path_ids(road_ids: str) -> str:
    return ",".join(quote(part.strip(), safe="") for part in road_ids.split(",") if part.strip())


def slim_road_status(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "displayName": item.get("displayName"),
        "statusSeverity": item.get("statusSeverity"),
        "statusSeverityDescription": item.get("statusSeverityDescription"),
    }


def slim_road_disruption(item: dict) -> dict:
    geo = item.get("geography") or {}
    coords = geo.get("coordinates") if isinstance(geo, dict) else None
    return {
        "id": item.get("id"),
        "location": item.get("location"),
        "comments": item.get("comments"),
        "currentUpdate": item.get("currentUpdate"),
        "severity": item.get("severity"),
        "category": item.get("category"),
        "hasClosures": item.get("hasClosures"),
        "corridorIds": item.get("corridorIds"),
        "coordinates": coords,
    }


def slim_street_disruption(item: dict) -> dict:
    return {
        "streetName": item.get("streetName"),
        "closure": item.get("closure"),
        "location": item.get("location"),
        "comments": item.get("comments"),
        "severity": item.get("severity"),
        "category": item.get("category"),
    }


def is_congested(status: dict) -> bool:
    desc = (status.get("statusSeverityDescription") or "").lower()
    severity = (status.get("statusSeverity") or "").lower()
    return desc not in ("no exceptional delays",) and severity not in ("good", "")


async def fetch_ev_charge_summary() -> dict[str, Any]:
    """Live EV connector counts from GET /Occupancy/ChargeConnector."""
    from collections import Counter

    data = await tfl_get("/Occupancy/ChargeConnector")
    counts = Counter(item.get("status") or "Unknown" for item in data)
    available = [c for c in data if c.get("status") == "Available"]
    return {
        "total_connectors": len(data),
        "available": counts.get("Available", 0),
        "charging": counts.get("Charging", 0),
        "out_of_service": counts.get("OutOfService", 0),
        "unknown": counts.get("Unknown", 0),
        "sample_available_ids": [c.get("sourceSystemPlaceId") for c in available[:5]],
    }


async def fetch_car_park_directory_summary() -> dict[str, Any]:
    """Static car park directory from GET /Place/Type/CarPark."""
    places = await tfl_get("/Place/Type/CarPark")
    total_spaces = 0
    for place in places:
        for ap in place.get("additionalProperties") or []:
            if ap.get("key") == "NumberOfSpaces" and ap.get("value"):
                try:
                    total_spaces += int(str(ap.get("value")).split(".")[0])
                except ValueError:
                    pass
    return {
        "total_car_parks": len(places),
        "total_listed_spaces": total_spaces,
        "live_occupancy_api_status": "unavailable",
        "live_occupancy_note": "GET /Occupancy/CarPark returns HTTP 500 from TfL (retried 2026-06-06)",
    }


async def fetch_parking_and_charging_snapshot() -> dict[str, Any]:
    """Combined EV live status + car park directory metadata."""
    ev, carparks = await _gather(fetch_ev_charge_summary(), fetch_car_park_directory_summary())
    return {"ev_charging": ev, "car_parks": carparks}


async def fetch_london_traffic_snapshot() -> dict[str, Any]:
    """Aggregate live Tube, road corridor, and street disruption data."""
    start_date, end_date = today_utc_range()
    (
        tube_status,
        tube_disruptions,
        road_status,
        all_road,
        street_disruptions,
        ev_summary,
        car_park_summary,
    ) = await _gather(
        tfl_get("/Line/Mode/tube/Status"),
        tfl_get("/Line/Mode/tube/Disruption"),
        tfl_get("/Road/all/Status"),
        tfl_get("/Road/all/Disruption"),
        tfl_get("/Road/all/Street/Disruption", {"startDate": start_date, "endDate": end_date}),
        fetch_ev_charge_summary(),
        fetch_car_park_directory_summary(),
    )

    not_good = [
        {
            "line": line.get("name"),
            "status": (line.get("lineStatuses") or [{}])[0].get("statusSeverityDescription"),
        }
        for line in tube_status
        if (line.get("lineStatuses") or [{}])[0].get("statusSeverityDescription") != "Good Service"
    ]

    congested = [slim_road_status(r) for r in road_status if is_congested(r)]
    road_issues = [
        slim_road_disruption(d)
        for d in all_road
        if d.get("severity") not in (None, "Minimal") or d.get("hasClosures")
    ][:10]
    closed_streets = [
        slim_street_disruption(s)
        for s in street_disruptions
        if (s.get("closure") or "").lower() not in ("open", "")
    ][:10]

    return {
        "tube": {
            "lines_not_good_service": not_good,
            "active_disruption_count": len(tube_disruptions),
            "disruption_summaries": [d.get("description") for d in tube_disruptions[:5]],
        },
        "roads": {
            "congested_corridors": congested,
            "congested_corridor_count": len(congested),
            "all_corridor_status": [slim_road_status(r) for r in road_status],
            "serious_disruption_count": len(road_issues),
            "top_disruptions": road_issues,
            "total_active_disruptions": len(all_road),
        },
        "streets": {
            "total_disrupted_segments": len(street_disruptions),
            "closed_or_restricted_count": len(closed_streets),
            "top_closed_streets": closed_streets,
        },
        "ev_charging": ev_summary,
        "car_parks": car_park_summary,
        "fetched_at": (
            tube_status[0].get("lineStatuses", [{}])[0].get("validTo") if tube_status else None
        ),
    }


LINE_NAME_TO_ID: dict[str, str] = {
    "bakerloo": "bakerloo",
    "central": "central",
    "circle": "circle",
    "district": "district",
    "hammersmith & city": "hammersmith-city",
    "jubilee": "jubilee",
    "metropolitan": "metropolitan",
    "northern": "northern",
    "piccadilly": "piccadilly",
    "victoria": "victoria",
    "waterloo & city": "waterloo-city",
}


def normalize_line_id(display_name: str) -> str:
    key = display_name.lower().strip().removesuffix(" line")
    if key in LINE_NAME_TO_ID:
        return LINE_NAME_TO_ID[key]
    return key.replace(" & ", "-").replace(" ", "-")


async def _gather(*awaitables: Any) -> tuple[Any, ...]:
    import asyncio

    return tuple(await asyncio.gather(*awaitables))
