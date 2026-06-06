"""
London Spatial MCP Server

Ward lookup, IMD deprivation profiles, and coordinate-to-ward resolution
for NV-Disruptron / NV-Disruptron.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Shared data module lives in repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.disruptron_data import (  # noqa: E402
    find_ward,
    load_wards,
    rank_wards_by_deprivation,
    search_wards,
    ward_to_dict,
    wards_by_borough,
)

load_dotenv()

mcp = FastMCP(
    "London Spatial Data",
    instructions=(
        "London ward boundaries, Index of Multiple Deprivation (IMD 2019), "
        "population, and borough GVA reference data. Use for spatial context "
        "when analysing transport disruption equity impacts across London."
    ),
)


@mcp.tool()
def get_data_status() -> dict:
    """Check whether London ward/IMD datasets are loaded."""
    try:
        wards = load_wards()
        return {
            "status": "ok",
            "ward_count": len(wards),
            "borough_count": len({w.borough for w in wards}),
            "data_source": "London Datastore — IMD 2019 ward summary measures",
        }
    except FileNotFoundError as exc:
        return {"status": "missing_data", "error": str(exc)}


@mcp.tool()
def search_london_wards(query: str, limit: int = 10) -> list[dict]:
    """Search London wards by name, borough, or ward code.

    Args:
        query: Ward name fragment, borough name, or ward code (e.g. 'Stonebridge', 'Brent', 'E05000103').
        limit: Maximum results (default 10).
    """
    return [ward_to_dict(w) for w in search_wards(query, limit=limit)]


@mcp.tool()
def get_ward_profile(ward: str) -> dict:
    """Get full deprivation and population profile for a London ward.

    Args:
        ward: Ward name or ward code (e.g. 'Golborne', 'Northumberland Park', 'E05000103').
    """
    record = find_ward(ward)
    if not record:
        matches = search_wards(ward, limit=5)
        if not matches:
            raise ValueError(f"No ward found for '{ward}'")
        if len(matches) > 1:
            return {
                "ambiguous": True,
                "message": f"Multiple wards match '{ward}'. Pick one:",
                "candidates": [ward_to_dict(w) for w in matches],
            }
        record = matches[0]
    return ward_to_dict(record)


@mcp.tool()
def list_wards_in_borough(borough: str) -> list[dict]:
    """List all wards in a London borough with IMD summary stats.

    Args:
        borough: Borough name (e.g. 'Hackney', 'Tower Hamlets', 'Kensington and Chelsea').
    """
    wards = wards_by_borough(borough)
    if not wards:
        raise ValueError(f"No wards found for borough '{borough}'")
    return [ward_to_dict(w) for w in sorted(wards, key=lambda w: w.imd_average_rank_rank)]


@mcp.tool()
def rank_most_deprived_wards(limit: int = 20, borough: str | None = None) -> list[dict]:
    """Rank London wards by deprivation (IMD 2019 average rank).

    Lower rank = more deprived. Use to identify vulnerable communities
    affected by transport disruption.

    Args:
        limit: Number of wards to return (default 20).
        borough: Optional borough filter (e.g. 'Haringey').
    """
    return [ward_to_dict(w) for w in rank_wards_by_deprivation(limit=limit, borough=borough)]


@mcp.tool()
async def lookup_ward_by_coordinates(latitude: float, longitude: float) -> dict:
    """Resolve the nearest London ward for a latitude/longitude pair.

    Uses postcodes.io reverse geocoding (no API key required), then matches
    to the local IMD ward dataset.

    Args:
        latitude: WGS84 latitude (e.g. 51.5074 for central London).
        longitude: WGS84 longitude (e.g. -0.1278).
    """
    url = "https://api.postcodes.io/postcodes"
    params = {"lon": longitude, "lat": latitude, "limit": 1, "radius": 2000}
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        payload = resp.json()

    results = payload.get("result") or []
    if not results:
        raise ValueError(f"No postcode/ward found near ({latitude}, {longitude})")

    nearest = results[0]
    admin_ward = nearest.get("admin_ward") or nearest.get("parish") or ""
    postcode = nearest.get("postcode", "")
    borough = nearest.get("admin_district") or nearest.get("parish") or ""

    ward_record = find_ward(admin_ward) if admin_ward else None
    if not ward_record and borough:
        borough_wards = wards_by_borough(borough)
        if len(borough_wards) == 1:
            ward_record = borough_wards[0]

    return {
        "input": {"latitude": latitude, "longitude": longitude},
        "nearest_postcode": postcode,
        "admin_ward": admin_ward,
        "borough": borough,
        "distance_metres": nearest.get("distance"),
        "ward_profile": ward_to_dict(ward_record) if ward_record else None,
    }


@mcp.tool()
async def lookup_ward_by_postcode(postcode: str) -> dict:
    """Look up ward and IMD profile from a UK postcode.

    Args:
        postcode: UK postcode (e.g. 'N17 0BX', 'SW1A 1AA').
    """
    clean = postcode.strip().replace(" ", "")
    url = f"https://api.postcodes.io/postcodes/{clean}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        payload = resp.json()

    result = payload.get("result")
    if not result:
        raise ValueError(f"Postcode not found: {postcode}")

    admin_ward = result.get("admin_ward", "")
    ward_record = find_ward(admin_ward) if admin_ward else None
    return {
        "postcode": result.get("postcode"),
        "admin_ward": admin_ward,
        "borough": result.get("admin_district"),
        "latitude": result.get("latitude"),
        "longitude": result.get("longitude"),
        "ward_profile": ward_to_dict(ward_record) if ward_record else None,
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
