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
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

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
        "This server provides access to the Transport for London (TfL) Unified API. "
        "Use it to check real-time and planned line disruptions for Tube, Overground, "
        "Elizabeth line, DLR, buses, and other modes. "
        "Prefer specific line IDs when the user mentions a particular line (e.g. 'victoria', 'jubilee'). "
        "Common modes: tube, overground, elizabeth-line, dlr, tram, bus."
    ),
)


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
