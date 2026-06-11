"""CKAN dataset ETL: CSV → GPU/CPU DataFrame → GeoParquet.

CPU fallback: pandas + geopandas (identical API surface, slower).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.gpu import GPU_AVAILABLE

if GPU_AVAILABLE:
    import cudf
    import cuspatial
else:
    import pandas as cudf  # type: ignore[no-redef]
    import geopandas as cuspatial  # type: ignore[no-redef]


def read_ckan_csv(path: str | Path) -> Any:
    """Load a CKAN CSV into a cuDF/pandas DataFrame.

    Auto-detects common column name variants and normalizes them.
    """
    df = cudf.read_csv(path)

    # Normalize common CKAN column names to snake_case
    rename_map: dict[str, str] = {}
    for col in df.columns:
        lower = str(col).lower().strip()
        if lower in ("ward code", "wardcode", "wd16cd"):
            rename_map[col] = "ward_code"
        elif lower in ("ward name", "wardname"):
            rename_map[col] = "ward_name"
        elif lower in ("borough", "lad16nm", "local authority"):
            rename_map[col] = "borough"
        elif lower in ("mobility difficulty %", "mobility_difficulty_pct"):
            rename_map[col] = "mobility_difficulty_pct"
        elif lower in ("dda disability %", "dda_disability_pct"):
            rename_map[col] = "dda_disability_pct"
        elif lower in ("fuel poverty %", "fuel_poverty_pct"):
            rename_map[col] = "fuel_poverty_pct"
        elif lower in ("crime rate", "crime_rate_per_1000"):
            rename_map[col] = "crime_rate_per_1000"
        elif lower in ("population", "total population"):
            rename_map[col] = "population"
        elif lower in ("lat", "latitude"):
            rename_map[col] = "lat"
        elif lower in ("lon", "longitude", "long"):
            rename_map[col] = "lon"

    if rename_map:
        df = df.rename(columns=rename_map)

    return df


def merge_ward_datasets(
    imd_path: str | Path,
    disability_path: str | Path | None = None,
    crime_path: str | Path | None = None,
    fuel_poverty_path: str | Path | None = None,
) -> Any:
    """Merge IMD + optional disability/crime/fuel-poverty into a single ward DataFrame.

    CPU/GPU agnostic — uses cuDF or pandas depending on availability.
    """
    base = read_ckan_csv(imd_path)

    if disability_path and Path(disability_path).exists():
        disability = read_ckan_csv(disability_path)
        cols = [c for c in ["ward_code", "mobility_difficulty_pct", "dda_disability_pct"] if c in disability.columns]
        if "ward_code" in cols:
            base = base.merge(disability[cols], on="ward_code", how="left")

    if crime_path and Path(crime_path).exists():
        crime = read_ckan_csv(crime_path)
        cols = [c for c in ["ward_code", "crime_rate_per_1000"] if c in crime.columns]
        if "ward_code" in cols:
            base = base.merge(crime[cols], on="ward_code", how="left")

    if fuel_poverty_path and Path(fuel_poverty_path).exists():
        fp = read_ckan_csv(fuel_poverty_path)
        # Fuel poverty is often borough-level; merge by borough
        cols = [c for c in ["borough", "fuel_poverty_pct"] if c in fp.columns]
        if "borough" in cols:
            base = base.merge(fp[cols], on="borough", how="left")

    return base


def to_geoparquet(df: Any, output_path: str | Path, crs: str = "EPSG:4326") -> Path:
    """Write DataFrame with lat/lon columns to GeoParquet.

    CPU fallback writes GeoJSON if geopandas is available.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if GPU_AVAILABLE and hasattr(df, "to_parquet"):
        # cuDF DataFrame — write plain parquet, add CRS metadata separately
        df["_crs"] = crs
        df.to_parquet(output_path)
        return output_path

    # CPU fallback: geopandas if lat/lon present
    if "lat" in df.columns and "lon" in df.columns:
        import geopandas as gpd
        from shapely.geometry import Point

        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df["lon"], df["lat"]),
            crs=crs,
        )
        gdf.to_parquet(output_path)
        return output_path

    # No geometry — plain parquet
    df.to_parquet(output_path)
    return output_path


def from_geoparquet(path: str | Path) -> Any:
    """Read GeoParquet into DataFrame."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"GeoParquet not found: {path}")

    if GPU_AVAILABLE:
        return cudf.read_parquet(path)

    import geopandas as gpd
    return gpd.read_parquet(path)
