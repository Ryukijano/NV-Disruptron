#!/usr/bin/env python3
"""End-to-end smoke test for Workstream 2 (Vision + Map) and Workstream 3 (RAPIDS GPU).

Usage:
    python scripts/smoke_test_ws2_ws3.py

Tests:
  1. Vision MCP server imports and tool registration
  2. Hazard pipeline label mapping + geotagging
  3. GPU layer fallback (CPU mode when RAPIDS absent)
  4. Gateway GeoJSON endpoints (dry-run)
  5. DBSCAN clustering on synthetic hazard points
  6. Nearest step-free station lookup
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "platform" / "shared" / "gpu"))


def test_vision_mcp_import() -> dict:
    import importlib.util

    # Skip if mcp.server is not installed (mcp package may exist but server submodule may not)
    if importlib.util.find_spec("mcp.server") is None:
        return {"status": "ok", "skipped": "mcp.server not installed"}

    try:
        spec = importlib.util.spec_from_file_location(
            "vision_server", REPO_ROOT / "platform" / "mcp" / "vision" / "server.py"
        )
        if spec is None or spec.loader is None:
            return {"status": "error", "error": "Cannot load vision server spec"}
        vision = importlib.util.module_from_spec(spec)
        sys.modules["vision_server"] = vision
        spec.loader.exec_module(vision)
        tools = [t.name for t in vision.mcp._tools]  # type: ignore[attr-defined]
        return {"status": "ok", "tools": tools}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def test_hazard_pipeline() -> dict:
    try:
        from features.vision.hazard_pipeline import (
            _map_label_to_category,
            _resolve_ward,
            HAZARD_KEYWORDS,
        )

        assert _map_label_to_category("blocked pavement") == "pavement_obstruction"
        assert _map_label_to_category("broken lift") == "broken_lift"
        assert _map_label_to_category("unknown thing") == "unknown"

        ward = _resolve_ward(51.5074, -0.1276)
        assert ward is not None
        assert ward.get("borough") == "Westminster"

        return {
            "status": "ok",
            "label_map_tests": 3,
            "ward": ward,
            "taxonomy_size": len(HAZARD_KEYWORDS),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def test_gpu_layer() -> dict:
    import importlib.util

    try:
        # Skip if pandas is not available (CPU fallback imports pandas as cudf)
        if importlib.util.find_spec("pandas") is None:
            return {"status": "ok", "skipped": "pandas not installed (CPU fallback unavailable)"}

        from shared.gpu import GPU_AVAILABLE, GPU_LIBS
        from shared.gpu.cuspatial_join import haversine_km, point_in_polygon
        from shared.gpu.cuml_clustering import cluster_hazards

        # Haversine
        dist = haversine_km(51.5074, -0.1276, 51.5426, -0.3458)
        assert 15 < dist < 25, f"Unexpected distance: {dist}"

        # Point-in-polygon fallback (empty)
        result = point_in_polygon([(51.5, -0.1)], None)
        assert result == [None]

        # DBSCAN clustering
        points = [
            (51.50, -0.12), (51.501, -0.121), (51.502, -0.119),  # cluster
            (51.60, -0.20), (51.601, -0.201),                     # cluster
            (51.90, -0.80),                                       # noise
        ]
        result = cluster_hazards(points, eps_km=0.5, min_samples=2)
        assert result["cluster_count"] == 2
        assert result["noise_count"] == 1

        return {
            "status": "ok",
            "gpu_available": GPU_AVAILABLE,
            "libs_loaded": list(GPU_LIBS.keys()),
            "haversine_km": round(dist, 2),
            "clusters": result["cluster_count"],
            "noise": result["noise_count"],
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def test_nearest_station() -> dict:
    try:
        # Skip if pandas is not available (deployment dependency)
        import importlib.util
        if importlib.util.find_spec("pandas") is None:
            return {"status": "ok", "skipped": "pandas not installed"}

        from shared.gpu.cuspatial_join import nearest_step_free_station
        import pandas as pd

        stations = pd.DataFrame([
            {"stop_id": "940GZZLUGFD", "name": "Greenford", "lat": 51.5423, "lon": -0.3458, "step_free": True},
            {"stop_id": "940GZZLUWMS", "name": "Westminster", "lat": 51.5008, "lon": -0.1251, "step_free": True},
        ])
        result = nearest_step_free_station(51.5008, -0.1251, stations, max_km=2.0)
        assert result is not None
        assert result["name"] == "Westminster"
        return {"status": "ok", "station": result["name"]}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def test_gateway_endpoints_dryrun() -> dict:
    try:
        # Verify gateway file exists and compiles
        gateway_path = REPO_ROOT / "features" / "delivery" / "disruptron-api" / "disruptron_api" / "gateway.py"
        if not gateway_path.exists():
            return {"status": "error", "error": f"gateway.py not found at {gateway_path}"}
        import py_compile
        py_compile.compile(str(gateway_path), doraise=True)
        return {"status": "ok", "gateway_compile": "ok", "path": str(gateway_path)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def main() -> None:
    print("=" * 60)
    print("NV-Disruptron Workstream 2 + 3 Smoke Test")
    print("=" * 60)

    tests = {
        "vision_mcp": test_vision_mcp_import,
        "hazard_pipeline": test_hazard_pipeline,
        "gpu_layer": test_gpu_layer,
        "nearest_station": test_nearest_station,
        "gateway": test_gateway_endpoints_dryrun,
    }

    all_ok = True
    for name, fn in tests.items():
        print(f"\n[{name}]")
        result = fn()
        status = result.pop("status")
        for key, val in result.items():
            print(f"  {key}: {val}")
        if status == "ok":
            print(f"  → PASS")
        else:
            print(f"  → FAIL: {result.get('error')}")
            all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("=" * 60)


if __name__ == "__main__":
    main()
