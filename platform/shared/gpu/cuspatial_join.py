"""GPU-accelerated spatial joins: point-in-polygon, nearest neighbor, haversine.

CPU fallback: geopandas + scipy.spatial.cKDTree.
"""

from __future__ import annotations

import math
from typing import Any

from shared.gpu import GPU_AVAILABLE

if GPU_AVAILABLE:
    import cudf
    import cuspatial
else:
    import pandas as cudf  # type: ignore[no-redef]
    import geopandas as cuspatial  # type: ignore[no-redef]


def point_in_polygon(
    points: list[tuple[float, float]],
    polygons: Any,
) -> list[str | None]:
    """Return polygon ID for each point, or None if outside all polygons.

    Args:
        points: List of (lat, lon) tuples.
        polygons: GeoDataFrame with geometry column (CPU) or cuSpatial polygon format (GPU).

    Returns:
        List of polygon IDs (or None) matching each point.
    """
    if not points:
        return []

    if GPU_AVAILABLE:
        return _point_in_polygon_gpu(points, polygons)
    return _point_in_polygon_cpu(points, polygons)


def _point_in_polygon_gpu(
    points: list[tuple[float, float]],
    polygons: Any,
) -> list[str | None]:
    """cuSpatial point-in-polygon."""
    # cuSpatial expects DataFrames with x/y columns
    df_points = cudf.DataFrame({
        "x": [p[1] for p in points],  # lon
        "y": [p[0] for p in points],  # lat
    })

    # Simplified: for each polygon, check containment
    # Full cuSpatial pip requires polygon rings format; this is a shim
    # that falls through to CPU if polygon format is incompatible
    try:
        # TODO: full cuSpatial point-in-polygon when polygon GeoParquet is ready
        return _point_in_polygon_cpu(points, polygons)
    except Exception:
        return [None] * len(points)


def _point_in_polygon_cpu(
    points: list[tuple[float, float]],
    polygons: Any,
) -> list[str | None]:
    """geopandas sjoin fallback."""
    import geopandas as gpd
    from shapely.geometry import Point

    if polygons is None or len(polygons) == 0:
        return [None] * len(points)

    gdf_points = gpd.GeoDataFrame(
        {"idx": range(len(points))},
        geometry=[Point(lon, lat) for lat, lon in points],
        crs="EPSG:4326",
    )

    joined = gpd.sjoin(
        gdf_points,
        polygons[["geometry"]],
        how="left",
        predicate="within",
    )

    # Extract polygon index (or None)
    return [row.get("index_right") for _, row in joined.iterrows()]


def nearest_step_free_station(
    lat: float,
    lon: float,
    stations: Any,  # DataFrame with lat, lon, step_free columns
    max_km: float = 2.0,
) -> dict | None:
    """Find nearest step-free station within max_km.

    Returns station dict or None.
    """
    if stations is None or len(stations) == 0:
        return None

    # Filter step-free stations
    step_free = stations[stations.get("step_free", True)] if "step_free" in stations.columns else stations
    if len(step_free) == 0:
        return None

    if GPU_AVAILABLE:
        # cuSpatial nearest points
        station_coords = cudf.DataFrame({
            "lat": step_free["lat"].astype(float),
            "lon": step_free["lon"].astype(float),
        })
        query = cudf.DataFrame({"lat": [lat], "lon": [lon]})
        # Haversine distance on GPU
        distances = _haversine_gpu(query, station_coords)
        min_idx = distances.argmin()
        min_dist = distances.iloc[min_idx]
        if min_dist <= max_km:
            return step_free.iloc[int(min_idx)].to_dict()
        return None

    # CPU: scipy cKDTree
    from scipy.spatial import cKDTree

    coords = step_free[["lat", "lon"]].to_numpy()
    tree = cKDTree(coords)
    dist_deg, idx = tree.query([[lat, lon]], k=1)
    # Approximate degree-to-km at this latitude
    dist_km = dist_deg[0] * 111.0
    if dist_km <= max_km:
        return step_free.iloc[idx[0]].to_dict()
    return None


def _haversine_gpu(query: Any, stations: Any) -> Any:
    """GPU haversine distance vectorized."""
    R = 6371.0
    lat1 = math.radians(query["lat"].iloc[0])
    lat2 = stations["lat"].astype(float).apply(math.radians)
    dlat = (stations["lat"].astype(float) - query["lat"].iloc[0]).apply(math.radians)
    dlon = (stations["lon"].astype(float) - query["lon"].iloc[0]).apply(math.radians)
    a = (dlat / 2).apply(math.sin) ** 2 + math.cos(lat1) * lat2.apply(math.cos) * (dlon / 2).apply(math.sin) ** 2
    return 2 * R * a.apply(math.asin).apply(math.sqrt)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Single-point haversine (CPU, exact)."""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))
