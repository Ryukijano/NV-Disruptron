"""NVIDIA cuOpt VRP solver for hazard-response crew routing.

Reads detected hazards from SQLite + depot locations → VRP → ordered crew routes.
Different from NeMo-Ray's set-cover mast placement: our cuOpt use = vehicle routing
from live CCTV-detected hazards to nearest response depots.

Usage:
    from platform.shared.gpu.cuopt_routing import plan_hazard_response_routes
    routes = plan_hazard_response_routes(hazard_ids=[1, 2, 3], depot_csv="depots.csv")
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np

from disruptron_api.config import REPO_ROOT

CUOPT_AVAILABLE = False
try:
    import cuopt_sh_client
    from cuopt_sh_client import CuOptServiceClient
    CUOPT_AVAILABLE = True
except Exception:
    pass

HAZARD_DB = REPO_ROOT / "data" / "hazards.db"


def _load_hazards_from_db(hazard_ids: list[int] | None = None) -> list[dict]:
    """Load hazard records from SQLite."""
    if not HAZARD_DB.exists():
        return []
    conn = sqlite3.connect(str(HAZARD_DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if hazard_ids:
        placeholders = ",".join("?" * len(hazard_ids))
        cur.execute(f"SELECT * FROM hazards WHERE id IN ({placeholders})", hazard_ids)
    else:
        cur.execute("SELECT * FROM hazards WHERE status = 'open' ORDER BY detected_at DESC LIMIT 50")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _load_depots(depot_csv: str | None = None) -> list[dict]:
    """Load response depot locations (LFB, council depots, etc.)."""
    if depot_csv and Path(depot_csv).exists():
        import csv
        depots = []
        with open(depot_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                depots.append({
                    "name": row.get("name", "depot"),
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                })
        return depots

    # Default: use known London fire stations from existing data
    default_depots = [
        {"name": "LFB Soho", "lat": 51.513, "lon": -0.131},
        {"name": "LFB Paddington", "lat": 51.518, "lon": -0.178},
        {"name": "LFB Stratford", "lat": 51.543, "lon": -0.002},
        {"name": "LFB Croydon", "lat": 51.372, "lon": -0.109},
        {"name": "LFB Kensington", "lat": 51.499, "lon": -0.194},
        {"name": "LFB Islington", "lat": 51.538, "lon": -0.103},
        {"name": "LFB Brixton", "lat": 51.461, "lon": -0.115},
        {"name": "LFB Hackney", "lat": 51.550, "lon": -0.055},
    ]
    return default_depots


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km."""
    from math import radians, sin, cos, sqrt, atan2
    R = 6371.0
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _build_distance_matrix(
    depots: list[dict], hazards: list[dict]
) -> tuple[np.ndarray, list[str], list[str]]:
    """Build distance matrix (km) between depots and hazards."""
    n_depots = len(depots)
    n_hazards = len(hazards)
    # Add a dummy depot 0 for cuOpt vehicle start
    n_nodes = 1 + n_depots + n_hazards
    matrix = np.zeros((n_nodes, n_nodes), dtype=np.float32)

    labels = ["START"] + [d["name"] for d in depots] + [h.get("label", f"haz_{i}") for i, h in enumerate(hazards)]

    # Build coordinate list
    coords = [(0.0, 0.0)]  # dummy start
    for d in depots:
        coords.append((d["lat"], d["lon"]))
    for h in hazards:
        coords.append((h.get("lat", 51.5), h.get("lon", -0.1)))

    for i in range(n_nodes):
        for j in range(n_nodes):
            if i != j:
                matrix[i, j] = _haversine_distance(
                    coords[i][0], coords[i][1], coords[j][0], coords[j][1]
                )

    return matrix, labels, coords


def plan_hazard_response_routes(
    hazard_ids: list[int] | None = None,
    depot_csv: str | None = None,
    max_vehicles: int = 3,
    vehicle_capacity: int = 5,
) -> dict[str, Any]:
    """Plan optimal crew dispatch routes from depots to hazards using cuOpt VRP.

    Args:
        hazard_ids: Specific hazards to respond to. If None, uses all open hazards.
        depot_csv: CSV with depot locations (name, lat, lon). Uses defaults if not provided.
        max_vehicles: Number of response vehicles available.
        vehicle_capacity: Max hazards per vehicle route.

    Returns:
        Dict with routes (ordered waypoints), total_distance_km, solver_status.
    """
    hazards = _load_hazards_from_db(hazard_ids)
    if not hazards:
        return {"status": "no_hazards", "routes": [], "total_distance_km": 0.0}

    depots = _load_depots(depot_csv)
    if not depots:
        return {"status": "no_depots", "routes": [], "total_distance_km": 0.0}

    matrix, labels, coords = _build_distance_matrix(depots, hazards)

    # If cuOpt not available, fall back to simple greedy nearest-neighbour
    if not CUOPT_AVAILABLE:
        return _greedy_routes(depots, hazards, labels, coords, max_vehicles, vehicle_capacity)

    try:
        return _cuopt_solve(matrix, labels, coords, max_vehicles, vehicle_capacity)
    except Exception as exc:
        # Fallback on cuOpt failure
        return _greedy_routes(depots, hazards, labels, coords, max_vehicles, vehicle_capacity)


def _cuopt_solve(
    matrix: np.ndarray,
    labels: list[str],
    coords: list[tuple],
    max_vehicles: int,
    vehicle_capacity: int,
) -> dict[str, Any]:
    """Solve VRP using NVIDIA cuOpt."""
    n_nodes = matrix.shape[0]
    n_hazards = n_nodes - 1 - len([l for l in labels if not l.startswith("haz") and l != "START"])

    # cuOpt JSON problem spec
    problem = {
        "objective": "minimize_distance",
        "vehicles": [
            {
                "id": v,
                "start_node": 0,
                "capacity": [vehicle_capacity],
            }
            for v in range(max_vehicles)
        ],
        "distance_matrix": matrix.tolist(),
        "depot_nodes": list(range(1, n_nodes - n_hazards)),
        "pickup_nodes": list(range(n_nodes - n_hazards, n_nodes)),
        "demand": [0] * (n_nodes - n_hazards) + [1] * n_hazards,
    }

    # Try local cuOpt server first
    try:
        client = CuOptServiceClient("http://localhost:8080")
        result = client.solve(problem)
    except Exception:
        # Fallback to hosted API if local not running
        api_key = os.getenv("CUOPT_API_KEY", "")
        if api_key:
            import requests
            resp = requests.post(
                "https://optimize.api.nvidia.com/v1/nvidia/cuopt",
                headers={"Authorization": f"Bearer {api_key}"},
                json=problem,
                timeout=30,
            )
            result = resp.json()
        else:
            raise RuntimeError("No local cuOpt server and no CUOPT_API_KEY")

    routes = []
    for v_route in result.get("routes", []):
        waypoints = []
        for node_idx in v_route.get("route", []):
            if node_idx < len(labels):
                waypoints.append({
                    "name": labels[node_idx],
                    "lat": coords[node_idx][0],
                    "lon": coords[node_idx][1],
                })
        if waypoints:
            routes.append({
                "vehicle_id": v_route.get("vehicle_id", 0),
                "waypoints": waypoints,
                "distance_km": v_route.get("distance", 0.0),
            })

    return {
        "status": "cuopt",
        "solver": "NVIDIA cuOpt",
        "routes": routes,
        "total_distance_km": sum(r["distance_km"] for r in routes),
        "vehicles_used": len(routes),
    }


def _greedy_routes(
    depots: list[dict],
    hazards: list[dict],
    labels: list[str],
    coords: list[tuple],
    max_vehicles: int,
    vehicle_capacity: int,
) -> dict[str, Any]:
    """Greedy nearest-neighbour fallback when cuOpt unavailable."""
    assigned = set()
    routes = []
    vehicle_id = 0

    for depot in depots[:max_vehicles]:
        if len(assigned) >= len(hazards):
            break
        route = [{"name": depot["name"], "lat": depot["lat"], "lon": depot["lon"]}]
        current_lat, current_lon = depot["lat"], depot["lon"]
        route_dist = 0.0

        for _ in range(vehicle_capacity):
            if len(assigned) >= len(hazards):
                break
            # Find nearest unassigned hazard
            best = None
            best_dist = float("inf")
            for i, haz in enumerate(hazards):
                if i in assigned:
                    continue
                d = _haversine_distance(current_lat, current_lon, haz.get("lat", 51.5), haz.get("lon", -0.1))
                if d < best_dist:
                    best_dist = d
                    best = i

            if best is not None:
                assigned.add(best)
                haz = hazards[best]
                route.append({
                    "name": haz.get("label", f"hazard_{best}"),
                    "lat": haz.get("lat", 51.5),
                    "lon": haz.get("lon", -0.1),
                    "category": haz.get("category", "unknown"),
                })
                route_dist += best_dist
                current_lat, current_lon = haz.get("lat", 51.5), haz.get("lon", -0.1)

        if len(route) > 1:
            routes.append({
                "vehicle_id": vehicle_id,
                "waypoints": route,
                "distance_km": round(route_dist, 2),
            })
            vehicle_id += 1

    return {
        "status": "greedy_fallback",
        "solver": "Greedy Nearest-Neighbour",
        "routes": routes,
        "total_distance_km": round(sum(r["distance_km"] for r in routes), 2),
        "vehicles_used": len(routes),
    }
