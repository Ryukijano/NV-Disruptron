"""GPU-accelerated hazard hotspot clustering with DBSCAN.

CPU fallback: sklearn.cluster.DBSCAN.
"""

from __future__ import annotations

from typing import Any

from shared.gpu import GPU_AVAILABLE

if GPU_AVAILABLE:
    import cuml
else:
    from sklearn.cluster import DBSCAN as cuml_DBSCAN  # type: ignore[attr-defined]


def cluster_hazards(
    points: list[tuple[float, float]],  # (lat, lon)
    eps_km: float = 0.2,  # 200m neighborhood
    min_samples: int = 3,
) -> dict[str, Any]:
    """DBSCAN clustering on hazard geotagged points.

    Returns:
        {
            "cluster_count": int,
            "noise_count": int,
            "hotspots": [
                {
                    "cluster_id": int,
                    "centroid": [lat, lon],
                    "point_count": int,
                    "radius_km": float,  # max distance from centroid
                }
            ]
        }
    """
    if not points:
        return {"cluster_count": 0, "noise_count": 0, "hotspots": []}

    if GPU_AVAILABLE:
        return _cluster_gpu(points, eps_km, min_samples)
    return _cluster_cpu(points, eps_km, min_samples)


def _cluster_gpu(
    points: list[tuple[float, float]],
    eps_km: float,
    min_samples: int,
) -> dict[str, Any]:
    """cuML DBSCAN on GPU."""
    import cudf
    import numpy as np

    # Convert lat/lon to approximate metres for Euclidean DBSCAN
    # At London latitudes: 1 deg lat ≈ 111km, 1 deg lon ≈ 70km
    coords = np.array(points)
    scaled = coords.copy()
    scaled[:, 0] *= 111000.0  # lat → metres
    scaled[:, 1] *= 70000.0   # lon → metres (approx at 51°N)

    df = cudf.DataFrame({"x": scaled[:, 0], "y": scaled[:, 1]})
    dbscan = cuml.DBSCAN(eps=eps_km * 1000, min_samples=min_samples)
    labels = dbscan.fit_predict(df)

    return _build_hotspot_summary(points, labels.to_numpy())


def _cluster_cpu(
    points: list[tuple[float, float]],
    eps_km: float,
    min_samples: int,
) -> dict[str, Any]:
    """sklearn DBSCAN on CPU."""
    import numpy as np
    from sklearn.cluster import DBSCAN

    coords = np.array(points)
    scaled = coords.copy()
    scaled[:, 0] *= 111000.0
    scaled[:, 1] *= 70000.0

    dbscan = DBSCAN(eps=eps_km * 1000, min_samples=min_samples)
    labels = dbscan.fit_predict(scaled)

    return _build_hotspot_summary(points, labels)


def _build_hotspot_summary(
    points: list[tuple[float, float]],
    labels: Any,
) -> dict[str, Any]:
    """Build human-readable hotspot summary from DBSCAN labels."""
    import numpy as np

    labels = np.array(labels)
    unique_labels = set(labels)
    noise_count = int(np.sum(labels == -1))
    cluster_ids = [l for l in unique_labels if l != -1]

    hotspots: list[dict] = []
    for cid in sorted(cluster_ids):
        mask = labels == cid
        cluster_points = np.array(points)[mask]
        centroid = [
            float(np.mean(cluster_points[:, 0])),
            float(np.mean(cluster_points[:, 1])),
        ]
        # Max distance from centroid
        dists = np.sqrt(
            (cluster_points[:, 0] - centroid[0]) ** 2 +
            (cluster_points[:, 1] - centroid[1]) ** 2
        )
        max_dist_deg = float(np.max(dists)) if len(dists) > 0 else 0.0
        # Approximate km (rough average at mid-latitudes)
        radius_km = max_dist_deg * 100.0

        hotspots.append({
            "cluster_id": int(cid),
            "centroid": centroid,
            "point_count": int(mask.sum()),
            "radius_km": round(radius_km, 3),
        })

    return {
        "cluster_count": len(cluster_ids),
        "noise_count": noise_count,
        "hotspots": hotspots,
    }
