"""Video ingestion pipeline for NV-Disruptron.

Processes video files/streams through LocateAnything-3B with temporal tracking
to detect *persistent* accessibility hazards and mobility disruptions.

Different from Argus:
- Argus: per-frame YOLO → vehicle counts → congestion prediction
- This: key-frame sampling → LocateAnything grounding → temporal tracking →
       persistent hazard events with onset/duration/location

Pipeline stages:
  1. Ingest: Accept video file or stream URL
  2. Sample: Extract key frames (scene-change + fixed-interval hybrid)
  3. Detect: LocateAnything-3B open-vocab grounding per frame
  4. Track: Temporal tracker links detections across time
  5. Eventify: Convert tracklets into persistent hazard events
  6. Geotag: If GPS metadata present, assign ward/borough
  7. Store: SQLite + GeoJSON + searchable event index
  8. Query: Natural language search over event descriptions
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from features.vision.hazard_pipeline import HAZARD_DB, HAZARD_GEOJSON, HAZARD_KEYWORDS, _map_label_to_category, _resolve_ward
from features.vision.locate_anything_client import get_client
from features.vision.temporal_tracker import TemporalTracker

REPO_ROOT = Path(__file__).resolve().parents[2]
VIDEO_DB = REPO_ROOT / "data" / "video_events.db"
VIDEO_GEOJSON = REPO_ROOT / "data" / "geo" / "video_events.geojson"


# ---------------------------------------------------------------------------
# Frame sampling
# ---------------------------------------------------------------------------

def sample_frames(video_path: str, target_fps: float = 0.5, min_scene_change: float = 0.25) -> list[tuple[int, float, np.ndarray]]:
    """Extract key frames from video using hybrid interval + scene-change detection.

    Args:
        video_path: Path to video file.
        target_fps: Target sampling rate (frames per second). Default 0.5 = 1 frame every 2 sec.
        min_scene_change: Minimum histogram diff (0-1) to trigger an extra keyframe.

    Returns:
        List of (frame_index, timestamp_seconds, rgb_array).
    """
    try:
        import cv2
    except ImportError:
        raise RuntimeError("OpenCV (cv2) required for video ingestion. Install: pip install opencv-python-headless")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    interval = max(1, int(video_fps / target_fps))

    frames: list[tuple[int, float, np.ndarray]] = []
    prev_hist = None
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        timestamp = frame_idx / video_fps
        is_key = (frame_idx % interval == 0)

        # Scene-change detection via histogram diff
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = cv2.normalize(hist, hist).flatten()

        if prev_hist is not None:
            diff = float(cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL))
            if diff < (1.0 - min_scene_change):
                is_key = True
        prev_hist = hist

        if is_key:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append((frame_idx, timestamp, rgb))

        frame_idx += 1

    cap.release()
    return frames


# ---------------------------------------------------------------------------
# Detection per frame
# ---------------------------------------------------------------------------

def _detect_frame(
    client: Any,
    rgb_array: np.ndarray,
    labels: list[str],
    threshold: float = 0.3,
) -> list[dict[str, Any]]:
    """Run LocateAnything on a single RGB frame."""
    from PIL import Image

    image = Image.fromarray(rgb_array)
    detections = client.detect(image, labels, threshold)

    results = []
    for det in detections:
        category = _map_label_to_category(det.label)
        results.append({
            "label": det.label,
            "category": category,
            "bbox": det.bbox,
            "confidence": det.confidence,
        })
    return results


# ---------------------------------------------------------------------------
# Main video analysis orchestrator
# ---------------------------------------------------------------------------

async def analyze_video(
    video_path: str | Path,
    lat: float | None = None,
    lon: float | None = None,
    target_fps: float = 0.5,
    confidence_threshold: float = 0.3,
    min_event_duration_sec: float = 1.0,
) -> dict[str, Any]:
    """Run the full video hazard detection pipeline.

    Args:
        video_path: Path to video file.
        lat: Optional latitude override.
        lon: Optional longitude override.
        target_fps: Frame sampling rate.
        confidence_threshold: Min detection confidence.
        min_event_duration_sec: Ignore events shorter than this.

    Returns:
        Summary dict with events, track count, and storage paths.
    """
    video_path = Path(video_path)
    client = get_client()
    all_labels = [kw for kws in HAZARD_KEYWORDS.values() for kw in kws]

    # 1. Sample frames
    frames = sample_frames(str(video_path), target_fps=target_fps)
    if not frames:
        return {"status": "no_frames_extracted", "events": []}

    # 2. Detect + track
    tracker = TemporalTracker(iou_threshold=0.45, max_missed_frames=3, min_track_length=2)
    for frame_idx, timestamp, rgb in frames:
        dets = _detect_frame(client, rgb, all_labels, confidence_threshold)
        tracker.update(dets, frame_idx, timestamp)

    # 3. Finalize tracks
    tracker.finalize()
    raw_events = tracker.get_all_events()
    persistent_events = tracker.get_persistent_events(min_duration_sec=min_event_duration_sec)

    # 4. Geotag if coordinates provided
    ward_info = None
    if lat is not None and lon is not None:
        ward_info = _resolve_ward(lat, lon)

    # 5. Persist
    _ensure_video_event_table()
    persisted_ids = []
    video_id = f"vid-{uuid.uuid4().hex[:8]}"
    timestamp_iso = datetime.now(UTC).isoformat()

    with sqlite3.connect(VIDEO_DB) as conn:
        for evt in persistent_events:
            event_id = evt["event_id"]
            persisted_ids.append(event_id)
            conn.execute(
                """
                INSERT OR REPLACE INTO video_events
                (event_id, video_id, category, label, start_frame, end_frame,
                 duration_sec, avg_confidence, frame_count, bbox_history,
                 lat, lon, ward, borough, timestamp, video_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    video_id,
                    evt["category"],
                    evt["label"],
                    evt["start_frame"],
                    evt["end_frame"],
                    evt["duration_sec"],
                    evt["avg_confidence"],
                    evt["frame_count"],
                    json.dumps(evt["bbox_history"]),
                    lat,
                    lon,
                    ward_info.get("ward") if ward_info else None,
                    ward_info.get("borough") if ward_info else None,
                    timestamp_iso,
                    str(video_path),
                ),
            )
        conn.commit()

    # 6. Rebuild GeoJSON
    _rebuild_video_geojson()

    return {
        "status": "analyzed",
        "video_id": video_id,
        "video_path": str(video_path),
        "frames_sampled": len(frames),
        "total_tracklets": len(raw_events),
        "persistent_events": len(persistent_events),
        "event_ids": persisted_ids,
        "categories": list({e["category"] for e in persistent_events}),
        "sqlite_path": str(VIDEO_DB),
        "geojson_path": str(VIDEO_GEOJSON),
        "lat": lat,
        "lon": lon,
    }


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _ensure_video_event_table() -> None:
    VIDEO_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(VIDEO_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS video_events (
                event_id TEXT PRIMARY KEY,
                video_id TEXT,
                category TEXT,
                label TEXT,
                start_frame INTEGER,
                end_frame INTEGER,
                duration_sec REAL,
                avg_confidence REAL,
                frame_count INTEGER,
                bbox_history TEXT,
                lat REAL,
                lon REAL,
                ward TEXT,
                borough TEXT,
                timestamp TEXT,
                video_path TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ve_category ON video_events(category)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ve_timestamp ON video_events(timestamp)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ve_video ON video_events(video_id)"
        )
        conn.commit()


def _rebuild_video_geojson() -> None:
    features: list[dict] = []
    if not VIDEO_DB.exists():
        return
    with sqlite3.connect(VIDEO_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM video_events WHERE lat IS NOT NULL AND lon IS NOT NULL ORDER BY timestamp DESC"
        ).fetchall()
        for row in rows:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [row["lon"], row["lat"]],
                },
                "properties": {
                    "event_id": row["event_id"],
                    "video_id": row["video_id"],
                    "category": row["category"],
                    "label": row["label"],
                    "duration_sec": row["duration_sec"],
                    "avg_confidence": row["avg_confidence"],
                    "frame_count": row["frame_count"],
                    "timestamp": row["timestamp"],
                    "ward": row["ward"],
                    "borough": row["borough"],
                },
            }
            features.append(feature)

    VIDEO_GEOJSON.parent.mkdir(parents=True, exist_ok=True)
    with VIDEO_GEOJSON.open("w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, indent=2)


# ---------------------------------------------------------------------------
# Query interface
# ---------------------------------------------------------------------------

def list_video_events(
    category: str | None = None,
    borough: str | None = None,
    min_duration_sec: float | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query persisted video events."""
    if not VIDEO_DB.exists():
        return []

    query = "SELECT * FROM video_events WHERE 1=1"
    params: list[Any] = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if borough:
        query += " AND borough = ?"
        params.append(borough)
    if min_duration_sec is not None:
        query += " AND duration_sec >= ?"
        params.append(min_duration_sec)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    with sqlite3.connect(VIDEO_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_event_timeline(video_id: str) -> list[dict[str, Any]]:
    """Get chronological event timeline for a specific video."""
    if not VIDEO_DB.exists():
        return []
    with sqlite3.connect(VIDEO_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM video_events WHERE video_id = ? ORDER BY start_frame",
            (video_id,),
        ).fetchall()
        return [dict(r) for r in rows]
