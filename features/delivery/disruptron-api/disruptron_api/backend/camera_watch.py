"""Shared camera detection helpers for agent-driven UI events.

Used by both the chat path (area-triggered detection popups) and the
autonomous watcher loop. Reuses the JamCam registry + LocateAnything-3B
pipeline already powering /v1/livefeed/cameras/{id}/analyze.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re

logger = logging.getLogger("disruptron.camera_watch")

TRAFFIC_LABELS = ["car", "bus", "person", "bicycle", "truck", "van", "motorcycle"]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _area_from_text(text: str) -> str | None:
    """Extract a London area name from user text (very naive)."""
    lower = text.lower()
    # Quick-trigger keywords
    if not any(
        kw in lower for kw in ["near", "in", "at", "around", "traffic", "camera", "cam", "stratford", "bank", "shoreditch", "camden", "hackney", "brixton", "islington", "kensington", "westminster", "city", "london bridge", "tottenham court", "oxford circus", "paddington", "euston", "kings cross", "waterloo"]
    ):
        return None
    # Try to pull a proper noun-ish word after near/in/at/around
    m = re.search(r"(?:near|in|at|around)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text)
    if m:
        return m.group(1)
    # Fallback: any known area word
    known = ["stratford", "bank", "shoreditch", "camden", "hackney", "brixton", "islington", "kensington", "westminster", "city", "london bridge", "tottenham court", "oxford circus", "paddington", "euston", "kings cross", "waterloo"]
    for k in known:
        if k in lower:
            return k.title()
    return None


def _cameras_near_area(registry: list[dict], area: str, limit: int = 3) -> list[dict]:
    """Return up to limit cameras whose name contains the area, or closest by rough match."""
    area_lower = area.lower()
    matches = [c for c in registry if area_lower in c.get("name", "").lower()]
    if matches:
        return matches[:limit]
    # Fallback: try partial token match
    tokens = area_lower.split()
    for t in tokens:
        if len(t) > 3:
            matches = [c for c in registry if t in c.get("name", "").lower()]
            if matches:
                return matches[:limit]
    return registry[:limit]


async def _analyze_camera(
    camera_id: str,
    labels: list[str] | None = None,
    confidence: float = 0.3,
) -> dict | None:
    """Run the same logic as the gateway analyze endpoint, returning a flat dict."""
    from features.vision.live_feed_pipeline import fetch_jamcam_registry, fetch_camera_snapshot
    from features.vision.locate_anything_client import get_client

    registry = await fetch_jamcam_registry()
    cam = None
    for c in registry:
        if c["id"] == camera_id or c["id"].endswith(camera_id):
            cam = c
            break
    if cam is None:
        logger.warning("Camera %s not found in registry", camera_id)
        return None

    image_url = cam.get("image_url")
    if not image_url:
        return None

    image = await fetch_camera_snapshot(image_url)
    if image is None:
        return None

    client = get_client()
    if labels is None:
        labels = TRAFFIC_LABELS
    detections = client.detect(image, labels, confidence_threshold=confidence)

    results = []
    for det in detections:
        results.append({"label": det.label, "bbox": det.bbox, "confidence": round(det.confidence, 3)})

    return {
        "camera_id": cam["id"],
        "camera_name": cam.get("name", cam["id"]),
        "lat": cam.get("lat", 51.5),
        "lon": cam.get("lon", -0.1),
        "image_url": image_url,
        "detections": results,
        "detection_count": len(results),
        "model": "LocateAnything-3B" if client.is_available() else "Nemotron-Omni-fallback",
    }


async def run_area_detection(
    area: str,
    labels: list[str] | None = None,
    max_cameras: int = 3,
) -> list[dict]:
    """Find cameras near an area and run detection on all. Returns list of result dicts."""
    from features.vision.live_feed_pipeline import fetch_jamcam_registry

    registry = await fetch_jamcam_registry()
    cameras = _cameras_near_area(registry, area, limit=max_cameras)
    if not cameras:
        return []

    tasks = [_analyze_camera(c["id"], labels=labels) for c in cameras]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]


async def sample_and_detect(
    camera_ids: list[str],
    labels: list[str] | None = None,
) -> list[dict]:
    """Run detection on a specific list of camera IDs."""
    tasks = [_analyze_camera(cid, labels=labels) for cid in camera_ids]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]
