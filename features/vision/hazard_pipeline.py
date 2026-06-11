"""Street-image hazard detection pipeline: Detect → Parse → Geotag → Store.

Stages:
  1. Detect: LocateAnything-3B / Nemotron grounding for hazard categories.
  2. Parse: Normalize bboxes, filter by confidence, map to hazard taxonomy.
  3. Geotag: EXIF GPS → cuSpatial point-in-polygon → ward/borough assignment.
  4. Store: Append to hazards.geoparquet / SQLite with metadata.

Usage:
    result = await analyze_street_image(image_path, lat=51.5, lon=-0.1)
    record = await report_hazard(result, user_id="anon")
"""

from __future__ import annotations

import base64
import csv
import json
import os
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from features.vision.locate_anything_client import DetectionResult, get_client

REPO_ROOT = Path(__file__).resolve().parents[2]
HAZARD_DB = REPO_ROOT / "data" / "hazards.db"
HAZARD_GEOJSON = REPO_ROOT / "data" / "geo" / "hazards.geojson"

# Normalized hazard taxonomy (open-vocab → canonical category)
HAZARD_KEYWORDS: dict[str, list[str]] = {
    "pavement_obstruction": [
        "blocked pavement", "blocked sidewalk", "obstructed path",
        "scaffolding on pavement", "construction blocking path",
    ],
    "broken_lift": [
        "broken lift", "out of service lift", "lift not working",
        "elevator broken", "lift outage",
    ],
    "missing_dropped_kerb": [
        "missing dropped kerb", "no dropped kerb", "curb not ramped",
    ],
    "flooding": [
        "flooding", "flood water", "standing water", "water on road",
    ],
    "illegal_parking": [
        "illegal parking", "car on pavement", "vehicle obstruction",
        "parking on sidewalk",
    ],
    "broken_ev_charger": [
        "broken ev charger", "out of service charger", "damaged charging point",
    ],
    "missing_tactile_paving": [
        "missing tactile paving", "no tactile paving", "tactile surface missing",
    ],
}


@dataclass
class HazardRecord:
    hazard_id: str
    category: str
    confidence: float
    lat: float | None
    lon: float | None
    ward_code: str | None
    borough: str | None
    timestamp: str
    image_path: str | None
    raw_label: str
    bbox: list[float] | None  # [x1,y1,x2,y2] normalized


def _map_label_to_category(label: str) -> str:
    """Map open-vocab label to canonical hazard category."""
    text = label.lower()
    for category, keywords in HAZARD_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "unknown"


def _extract_exif_gps(image_path: str | Path) -> tuple[float, float] | None:
    """Extract GPS coordinates from image EXIF if present."""
    try:
        from PIL import Image
        from PIL.ExifTags import GPSTAGS, TAGS

        img = Image.open(image_path)
        exif = img._getexif()
        if not exif:
            return None

        def _get_tag(tag_name: str) -> Any:
            for tag_id, value in exif.items():
                if TAGS.get(tag_id) == tag_name:
                    return value
            return None

        def _get_gps_tag(tag_name: str) -> Any:
            gps_info = _get_tag("GPSInfo")
            if not gps_info:
                return None
            for key, val in GPSTAGS.items():
                if val == tag_name:
                    return gps_info.get(key)
            return None

        def _to_degrees(value: tuple) -> float:
            d, m, s = value
            return float(d) + float(m) / 60 + float(s) / 3600

        lat_ref = _get_gps_tag("GPSLatitudeRef")
        lat = _get_gps_tag("GPSLatitude")
        lon_ref = _get_gps_tag("GPSLongitudeRef")
        lon = _get_gps_tag("GPSLongitude")

        if lat and lon and lat_ref and lon_ref:
            lat_deg = _to_degrees(lat)
            lon_deg = _to_degrees(lon)
            if lat_ref == "S":
                lat_deg = -lat_deg
            if lon_ref == "W":
                lon_deg = -lon_deg
            return (lat_deg, lon_deg)
    except Exception:
        pass
    return None


def _resolve_ward(lat: float, lon: float) -> dict | None:
    """Reverse geocode lat/lon to ward using postcodes.io."""
    import httpx

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                "https://api.postcodes.io/postcodes",
                params={"lon": lon, "lat": lat, "limit": 1, "radius": 1500},
            )
            resp.raise_for_status()
            results = resp.json().get("result") or []
            if results:
                return {
                    "ward": results[0].get("admin_ward"),
                    "borough": results[0].get("admin_district"),
                    "postcode": results[0].get("postcode"),
                }
    except Exception:
        pass
    return None


def _ensure_hazard_table() -> None:
    """Create SQLite hazards table if not exists."""
    HAZARD_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(HAZARD_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS hazards (
                hazard_id TEXT PRIMARY KEY,
                category TEXT,
                confidence REAL,
                lat REAL,
                lon REAL,
                ward_code TEXT,
                borough TEXT,
                timestamp TEXT,
                image_path TEXT,
                raw_label TEXT,
                bbox TEXT
            )
            """
        )
        conn.commit()


async def analyze_street_image(
    image_path: str | Path,
    lat: float | None = None,
    lon: float | None = None,
    confidence_threshold: float = 0.3,
) -> list[HazardRecord]:
    """Run the full 4-stage hazard detection pipeline on a street image.

    Args:
        image_path: Path to image file.
        lat: Optional explicit latitude (overrides EXIF).
        lon: Optional explicit longitude (overrides EXIF).
        confidence_threshold: Min detection confidence.

    Returns:
        List of HazardRecord (may be empty if no hazards detected).
    """
    image_path = Path(image_path)

    # --- Stage 3 pre-work: geolocation ---
    if lat is None or lon is None:
        gps = _extract_exif_gps(image_path)
        if gps:
            lat, lon = gps

    # --- Stage 1: Detect ---
    client = get_client()
    all_labels = [kw for kws in HAZARD_KEYWORDS.values() for kw in kws]
    detections: list[DetectionResult] = client.detect(
        str(image_path), all_labels, confidence_threshold
    )

    if not detections:
        return []

    # --- Stage 3: Geotag (reverse geocode if lat/lon present) ---
    ward_info: dict | None = None
    if lat is not None and lon is not None:
        ward_info = _resolve_ward(lat, lon)

    # --- Stage 2: Parse + Stage 4: Store prep ---
    timestamp = datetime.now(UTC).isoformat()
    records: list[HazardRecord] = []

    for det in detections:
        category = _map_label_to_category(det.label)
        record = HazardRecord(
            hazard_id=str(uuid.uuid4())[:8],
            category=category,
            confidence=det.confidence,
            lat=lat,
            lon=lon,
            ward_code=ward_info.get("ward") if ward_info else None,
            borough=ward_info.get("borough") if ward_info else None,
            timestamp=timestamp,
            image_path=str(image_path),
            raw_label=det.label,
            bbox=det.bbox,
        )
        records.append(record)

    return records


async def report_hazard(
    records: list[HazardRecord],
    user_id: str = "anonymous",
) -> dict:
    """Persist detected hazards to SQLite + GeoJSON FeatureCollection.

    Returns:
        Summary dict with persisted count and file paths.
    """
    _ensure_hazard_table()
    persisted = 0

    with sqlite3.connect(HAZARD_DB) as conn:
        for r in records:
            conn.execute(
                """
                INSERT OR REPLACE INTO hazards
                (hazard_id, category, confidence, lat, lon, ward_code, borough,
                 timestamp, image_path, raw_label, bbox)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r.hazard_id,
                    r.category,
                    r.confidence,
                    r.lat,
                    r.lon,
                    r.ward_code,
                    r.borough,
                    r.timestamp,
                    r.image_path,
                    r.raw_label,
                    json.dumps(r.bbox) if r.bbox else None,
                ),
            )
            persisted += 1
        conn.commit()

    # Update GeoJSON for frontend map layer
    geojson = _build_hazard_geojson()
    HAZARD_GEOJSON.parent.mkdir(parents=True, exist_ok=True)
    with HAZARD_GEOJSON.open("w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)

    return {
        "persisted_count": persisted,
        "total_records": _count_hazards(),
        "sqlite_path": str(HAZARD_DB),
        "geojson_path": str(HAZARD_GEOJSON),
        "user_id": user_id,
    }


def _build_hazard_geojson() -> dict:
    """Build GeoJSON FeatureCollection from SQLite hazards."""
    features: list[dict] = []
    if not HAZARD_DB.exists():
        return {"type": "FeatureCollection", "features": features}

    with sqlite3.connect(HAZARD_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM hazards ORDER BY timestamp DESC").fetchall()
        for row in rows:
            if row["lat"] is None or row["lon"] is None:
                continue
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [row["lon"], row["lat"]],
                },
                "properties": {
                    "hazard_id": row["hazard_id"],
                    "category": row["category"],
                    "confidence": row["confidence"],
                    "ward_code": row["ward_code"],
                    "borough": row["borough"],
                    "timestamp": row["timestamp"],
                    "raw_label": row["raw_label"],
                },
            }
            features.append(feature)

    return {"type": "FeatureCollection", "features": features}


def _count_hazards() -> int:
    if not HAZARD_DB.exists():
        return 0
    with sqlite3.connect(HAZARD_DB) as conn:
        row = conn.execute("SELECT COUNT(*) FROM hazards").fetchone()
        return row[0] if row else 0


def list_hazard_hotspots(
    category: str | None = None,
    borough: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Query hazard records with optional filters."""
    if not HAZARD_DB.exists():
        return []

    query = "SELECT * FROM hazards WHERE 1=1"
    params: list[Any] = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if borough:
        query += " AND borough = ?"
        params.append(borough)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    with sqlite3.connect(HAZARD_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
