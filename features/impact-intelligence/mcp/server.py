"""
London Impact MCP Server

Scores transport disruption impact by combining TfL live data with
London ward deprivation (IMD) and population/GVA weighting.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.lifeline_data import (  # noqa: E402
    compute_impact_score,
    find_ward,
    infer_severity_weight,
    load_wards,
    rank_wards_by_deprivation,
    ward_to_dict,
)

load_dotenv()

TFL_BASE_URL = "https://api.tfl.gov.uk"
TFL_APP_KEY = os.getenv("TFL_APP_KEY", "").strip()

mcp = FastMCP(
    "London Disruption Impact",
    instructions=(
        "Quantify transport disruption equity and economic exposure across London. "
        "Combines TfL line status/disruptions with IMD deprivation weighting, "
        "population normalization, and borough GVA estimates. "
        "Use after fetching live disruption data from the TfL MCP server."
    ),
)


def _tfl_params(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if TFL_APP_KEY:
        params["app_key"] = TFL_APP_KEY
    if extra:
        params.update(extra)
    return params


async def _tfl_get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{TFL_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=_tfl_params(params))
        resp.raise_for_status()
        return resp.json()


async def _resolve_ward_at_point(lat: float, lon: float) -> dict | None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(
            "https://api.postcodes.io/postcodes",
            params={"lon": lon, "lat": lat, "limit": 1, "radius": 1500},
        )
        resp.raise_for_status()
        results = resp.json().get("result") or []
    if not results:
        return None
    admin_ward = results[0].get("admin_ward", "")
    ward = find_ward(admin_ward) if admin_ward else None
    return ward_to_dict(ward) if ward else {"admin_ward": admin_ward, "borough": results[0].get("admin_district")}


async def _stations_for_line(line_id: str) -> list[dict]:
    """Fetch ordered stations on a TfL line."""
    data = await _tfl_get(f"/Line/{line_id.strip()}/Route/Sequence/all")
    raw_stops: list[dict] = []

    # Modern TfL API shape (stations + stopPointSequences)
    for stop in data.get("stations") or []:
        raw_stops.append(stop)
    for sequence in data.get("stopPointSequences") or []:
        raw_stops.extend(sequence.get("stopPoint") or [])

    # Legacy inbound/outbound shape
    for direction in ("inbound", "outbound"):
        raw_stops.extend(data.get(direction) or [])

    stations: list[dict] = []
    for stop in raw_stops:
        if stop.get("stopType") == "Lap":
            continue
        lat = stop.get("lat")
        lon = stop.get("lon")
        if lat is None or lon is None:
            continue
        stations.append(
            {
                "id": stop.get("id"),
                "name": stop.get("name"),
                "lat": lat,
                "lon": lon,
            }
        )

    seen: set[str] = set()
    unique: list[dict] = []
    for station in stations:
        sid = station.get("id") or station["name"]
        if sid in seen:
            continue
        seen.add(sid)
        unique.append(station)
    return unique


async def _wards_along_line(line_id: str) -> list[dict]:
    stations = await _stations_for_line(line_id)
    profiles = await asyncio.gather(
        *[_resolve_ward_at_point(s["lat"], s["lon"]) for s in stations],
        return_exceptions=True,
    )
    ward_profiles: dict[str, dict] = {}
    for station, profile in zip(stations, profiles):
        if isinstance(profile, Exception) or not profile or not profile.get("ward_code"):
            continue
        ward_profiles[profile["ward_code"]] = {**profile, "via_station": station["name"]}
    return list(ward_profiles.values())


@mcp.tool()
def get_impact_data_status() -> dict:
    """Health check for impact scoring datasets and TfL API key."""
    try:
        wards = load_wards()
        return {
            "status": "ok",
            "ward_count": len(wards),
            "tfl_app_key_configured": bool(TFL_APP_KEY),
            "methodology": "impact_index = imd_extent × deprivation_quintile_weight × severity",
        }
    except FileNotFoundError as exc:
        return {"status": "missing_data", "error": str(exc)}


@mcp.tool()
async def map_line_to_wards(line_id: str) -> dict:
    """Map a TfL line to the London wards its stations pass through.

    Args:
        line_id: TfL line ID (e.g. 'jubilee', 'victoria', 'northern', 'elizabeth').
    """
    wards = await _wards_along_line(line_id)
    return {
        "line_id": line_id,
        "ward_count": len(wards),
        "wards": sorted(wards, key=lambda w: w.get("imd_deprivation_rank", 9999)),
    }


@mcp.tool()
async def rank_vulnerable_wards_on_line(line_id: str, limit: int = 15) -> list[dict]:
    """Rank wards along a TfL line by deprivation (most vulnerable first).

    Args:
        line_id: TfL line ID (e.g. 'jubilee', 'central').
        limit: Max wards to return.
    """
    wards = await _wards_along_line(line_id)
    wards = [w for w in wards if w.get("imd_deprivation_rank")]
    wards.sort(key=lambda w: w["imd_deprivation_rank"])
    return wards[:limit]


@mcp.tool()
async def score_line_disruption_impact(line_id: str) -> dict:
    """Score disruption impact for a TfL line using live status + IMD weighting.

    Fetches current line status/disruptions from TfL, maps the line to wards,
    and computes a composite impact index per ward.

    Args:
        line_id: TfL line ID (e.g. 'jubilee', 'victoria', 'northern').
    """
    status_list = await _tfl_get(f"/Line/{line_id.strip()}/Status")
    disruptions = await _tfl_get(f"/Line/{line_id.strip()}/Disruption")

    if not status_list:
        raise ValueError(f"No status returned for line '{line_id}'")

    line_status = status_list[0]
    status_text = " | ".join(
        ls.get("statusSeverityDescription", "") for ls in line_status.get("lineStatuses", [])
    )
    severity = infer_severity_weight(status_text)
    if disruptions:
        for d in disruptions:
            severity = max(severity, infer_severity_weight(
                d.get("description", ""),
                d.get("closureText", ""),
            ))

    wards_on_line = await _wards_along_line(line_id)
    ward_records = []
    for w in wards_on_line:
        ward = find_ward(w.get("ward_code") or w.get("ward_name", ""))
        if ward:
            ward_records.append(compute_impact_score(ward, severity))

    ward_records.sort(key=lambda x: x["impact_index"], reverse=True)

    return {
        "line_id": line_id,
        "line_name": line_status.get("name"),
        "current_status": status_text,
        "severity_weight": round(severity, 3),
        "active_disruptions": len(disruptions or []),
        "disruption_summaries": [
            d.get("description") for d in (disruptions or [])[:5]
        ],
        "wards_analysed": len(ward_records),
        "top_impacted_wards": ward_records[:15],
        "methodology": {
            "severity": "Inferred from TfL status + disruption text",
            "vulnerability": "IMD extent % × deprivation quintile weight",
            "economic": "working_age_pop × severity × borough GVA/job",
        },
    }


@mcp.tool()
async def compare_lines_disruption_impact(line_ids: str) -> list[dict]:
    """Compare disruption impact scores across multiple TfL lines.

    Args:
        line_ids: Comma-separated line IDs (e.g. 'jubilee,victoria,northern').
    """
    results = []
    for line_id in [x.strip() for x in line_ids.split(",") if x.strip()]:
        try:
            scored = await score_line_disruption_impact(line_id)
            top = scored.get("top_impacted_wards") or []
            max_impact = top[0]["impact_index"] if top else 0.0
            results.append(
                {
                    "line_id": line_id,
                    "line_name": scored.get("line_name"),
                    "current_status": scored.get("current_status"),
                    "severity_weight": scored.get("severity_weight"),
                    "max_ward_impact_index": max_impact,
                    "wards_analysed": scored.get("wards_analysed"),
                    "top_ward": top[0] if top else None,
                }
            )
        except Exception as exc:  # noqa: BLE001 — surface per-line errors to agent
            results.append({"line_id": line_id, "error": str(exc)})
    results.sort(key=lambda x: x.get("max_ward_impact_index", 0), reverse=True)
    return results


@mcp.tool()
def estimate_citywide_vulnerability_exposure(severity: float = 0.75, limit: int = 25) -> dict:
    """Estimate citywide exposure if all top-deprived wards faced a given disruption severity.

    Useful for scenario planning when a major line is suspended.

    Args:
        severity: Disruption severity weight 0.0–1.0 (default 0.75 = severe delays).
        limit: Number of top wards to include in the breakdown.
    """
    severity = max(0.0, min(1.0, severity))
    top_wards = rank_wards_by_deprivation(limit=limit)
    scored = [compute_impact_score(w, severity) for w in top_wards]
    total_economic = sum(s["economic_exposure_gbp_k_per_hour"] for s in scored)
    total_pop = sum(s["commuters_estimated"] for s in scored)
    return {
        "scenario_severity": severity,
        "wards_in_scenario": len(scored),
        "total_working_age_population": total_pop,
        "total_economic_exposure_gbp_k_per_hour": round(total_economic, 2),
        "top_exposed_wards": scored,
        "note": "Scenario model for most-deprived wards; not a live TfL feed.",
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
