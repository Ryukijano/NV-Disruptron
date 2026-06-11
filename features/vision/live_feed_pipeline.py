"""Live TfL JamCam feed pipeline for real-time accessibility monitoring.

Different from Argus:
- Argus: Raw CCTV streams → YOLO11x per-frame → vehicle counts → congestion cascade prediction
- This: TfL JamCam JPEG snapshots → Nemotron Omni multimodal reasoning →
       accessibility/mobility insights (crowd density, step-free blockages,
       platform conditions, incident detection)

Architecture:
  1. Fetch camera registry from TfL Unified API
  2. Poll key cameras near stations (configurable subset)
  3. Compile N snapshots into a short video clip
  4. Send to Nemotron Omni for scene understanding + reasoning
  5. Extract structured insights (crowd_level, accessibility_status, hazards)
  6. Store as live observations → update map layer + trigger alerts
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from PIL import Image

NEMOTRON_URL = os.getenv("NEMOTRON_URL", "http://localhost:8008/v1")
TFL_APP_KEY = os.getenv("TFL_APP_KEY", "")
TFL_BASE = "https://api.tfl.gov.uk"

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_FEED_DB = REPO_ROOT / "data" / "live_feed_observations.db"


# ---------------------------------------------------------------------------
# TfL JamCam registry + snapshot fetching
# ---------------------------------------------------------------------------

async def fetch_jamcam_registry() -> list[dict[str, Any]]:
    """Fetch all JamCam locations from TfL Unified API.

    Returns list of camera dicts with id, lat, lon, name, imageUrl, videoUrl.
    """
    url = f"{TFL_BASE}/Place/Type/JamCam/"
    params = {}
    if TFL_APP_KEY:
        params["app_key"] = TFL_APP_KEY

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    cameras = []
    for place in data:
        cam_id = place.get("id", "")
        if not cam_id.startswith("JamCam"):
            continue

        lat = place.get("lat")
        lon = place.get("lon")
        name = place.get("commonName", cam_id)

        image_url = None
        video_url = None
        available = None
        for prop in place.get("additionalProperties", []):
            if prop.get("key") == "imageUrl":
                image_url = prop.get("value")
            elif prop.get("key") == "videoUrl":
                video_url = prop.get("value")
            elif prop.get("key") == "available":
                available = prop.get("value") == "true"

        if image_url:
            cameras.append({
                "id": cam_id,
                "name": name,
                "lat": lat,
                "lon": lon,
                "image_url": image_url,
                "video_url": video_url,
                "available": available,
            })

    return cameras


async def fetch_camera_snapshot(image_url: str) -> Image.Image | None:
    """Fetch a single JPEG snapshot from a JamCam."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(image_url)
            resp.raise_for_status()
            return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception as exc:
        print(f"Snapshot fetch failed for {image_url}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Build video clip from snapshots for Nemotron Omni
# ---------------------------------------------------------------------------

def build_video_from_snapshots(
    snapshots: list[Image.Image],
    fps: float = 1.0,
    output_path: str | None = None,
) -> str:
    """Compile JPEG snapshots into an MP4 video for Nemotron Omni input.

    Args:
        snapshots: List of PIL RGB images.
        fps: Frames per second in output video.
        output_path: Optional output path; temp file if None.

    Returns:
        Path to generated MP4 file.
    """
    try:
        import cv2
    except ImportError:
        raise RuntimeError("OpenCV required. pip install opencv-python-headless")

    if not snapshots:
        raise ValueError("No snapshots provided")

    if output_path is None:
        suffix = f"_livefeed_{uuid.uuid4().hex[:8]}.mp4"
        output_path = tempfile.mktemp(suffix=suffix)

    w, h = snapshots[0].size
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    for img in snapshots:
        rgb = np.array(img)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        writer.write(bgr)

    writer.release()
    return output_path


# ---------------------------------------------------------------------------
# Nemotron Omni scene analysis
# ---------------------------------------------------------------------------

async def analyze_scene_with_nemotron(
    video_path: str,
    camera_name: str,
    camera_id: str,
) -> dict[str, Any]:
    """Send video clip to Nemotron Omni for accessibility/mobility scene understanding.

    Prompts Nemotron to reason about:
      - Crowd density level (low/moderate/high/critical)
      - Step-free access status (clear / partially blocked / fully blocked)
      - Visible hazards (flooding, construction, obstacles)
      - Platform/station condition summary
      - Recommended action for mobility-impaired travelers

    Returns structured insight dict.
    """
    # Read video as base64
    with open(video_path, "rb") as f:
        video_b64 = base64.b64encode(f.read()).decode()

    prompt = (
        f"You are an AI accessibility monitor analyzing CCTV footage from {camera_name} ({camera_id}).\n"
        "Watch this short video clip and analyze the scene for mobility and accessibility conditions.\n\n"
        "Provide a structured JSON response with these exact fields:\n"
        "{\n"
        '  "crowd_density": "low|moderate|high|critical",\n'
        '  "step_free_access": "clear|partially_blocked|fully_blocked|unknown",\n'
        '  "visible_hazards": ["none"] or list like ["construction barrier", "flooding", "pavement obstruction"],\n'
        '  "platform_condition": "normal|crowded|congested|disrupted",\n'
        '  "mobility_impact": "none|minor|moderate|severe",\n'
        '  "recommended_action": "brief recommendation for wheelchair users or mobility-impaired travelers",\n'
        '  "confidence": 0.0 to 1.0\n'
        "}\n\n"
        "Be precise and evidence-based. If you cannot determine something, use 'unknown'."
    )

    messages = [
        {"role": "system", "content": "You are a multimodal accessibility analyst. Respond only in valid JSON."},
        {
            "role": "user",
            "content": [
                {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{video_b64}"}},
                {"type": "text", "text": prompt},
            ],
        },
    ]

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{NEMOTRON_URL}/chat/completions",
                json={
                    "model": "nemotron-omni",
                    "messages": messages,
                    "max_tokens": 512,
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return _extract_json(content)
    except Exception as exc:
        print(f"Nemotron analysis failed: {exc}")
        return {
            "crowd_density": "unknown",
            "step_free_access": "unknown",
            "visible_hazards": ["analysis_failed"],
            "platform_condition": "unknown",
            "mobility_impact": "unknown",
            "recommended_action": "Analysis failed; rely on other data sources.",
            "confidence": 0.0,
            "error": str(exc),
        }


def _extract_json(text: str) -> dict[str, Any]:
    """Extract JSON object from markdown/text response."""
    import re
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {"raw_response": text, "error": "JSON parse failed"}


# ---------------------------------------------------------------------------
# Orchestrator: poll cameras → analyze → persist
# ---------------------------------------------------------------------------

async def run_live_feed_cycle(
    camera_ids: list[str] | None = None,
    poll_interval_sec: int = 120,
    snapshots_per_camera: int = 3,
    snapshot_delay_sec: float = 5.0,
) -> list[dict[str, Any]]:
    """Run one monitoring cycle: fetch snapshots, build clips, analyze with Nemotron.

    Args:
        camera_ids: Specific camera IDs to monitor; if None, auto-selects near stations.
        poll_interval_sec: Time between full cycles.
        snapshots_per_camera: How many snapshots to collect per camera per cycle.
        snapshot_delay_sec: Delay between snapshot fetches for motion context.

    Returns:
        List of observation records.
    """
    # 1. Get camera registry
    registry = await fetch_jamcam_registry()
    if not registry:
        return []

    # 2. Select cameras
    if camera_ids:
        selected = [c for c in registry if c["id"] in camera_ids]
    else:
        # Auto-select cameras with names suggesting station/transport proximity
        station_keywords = ["station", "underground", "tube", "interchange", "platform",
                            "bank", "stratford", "canary wharf", "liverpool street",
                            "kings cross", "waterloo", "paddington", "victoria"]
        selected = [
            c for c in registry
            if any(kw in c["name"].lower() for kw in station_keywords)
        ]
        # Fallback: just take first 20 if none matched
        if not selected:
            selected = registry[:20]

    observations: list[dict[str, Any]] = []

    for cam in selected:
        cam_id = cam["id"]
        print(f"[LiveFeed] Polling {cam_id} — {cam['name']}")

        # 3. Collect snapshots
        snapshots: list[Image.Image] = []
        for _ in range(snapshots_per_camera):
            img = await fetch_camera_snapshot(cam["image_url"])
            if img:
                snapshots.append(img)
            if snapshot_delay_sec > 0 and _ < snapshots_per_camera - 1:
                await asyncio.sleep(snapshot_delay_sec)

        if len(snapshots) < 2:
            print(f"[LiveFeed] Insufficient snapshots for {cam_id}")
            continue

        # 4. Build video clip
        try:
            video_path = build_video_from_snapshots(snapshots, fps=1.0)
        except Exception as exc:
            print(f"[LiveFeed] Video build failed for {cam_id}: {exc}")
            continue

        # 5. Analyze with Nemotron
        insight = await analyze_scene_with_nemotron(video_path, cam["name"], cam_id)

        # 6. Build observation record
        observation = {
            "observation_id": f"obs-{uuid.uuid4().hex[:8]}",
            "camera_id": cam_id,
            "camera_name": cam["name"],
            "lat": cam["lat"],
            "lon": cam["lon"],
            "timestamp": datetime.now(UTC).isoformat(),
            "snapshot_count": len(snapshots),
            "crowd_density": insight.get("crowd_density", "unknown"),
            "step_free_access": insight.get("step_free_access", "unknown"),
            "visible_hazards": insight.get("visible_hazards", []),
            "platform_condition": insight.get("platform_condition", "unknown"),
            "mobility_impact": insight.get("mobility_impact", "unknown"),
            "recommended_action": insight.get("recommended_action", ""),
            "confidence": insight.get("confidence", 0.0),
            "raw_insight": insight,
        }
        observations.append(observation)

        # Cleanup temp video
        try:
            Path(video_path).unlink(missing_ok=True)
        except Exception:
            pass

    # 7. Persist
    _ensure_observation_table()
    with sqlite3.connect(LIVE_FEED_DB) as conn:
        for obs in observations:
            conn.execute(
                """
                INSERT INTO live_observations
                (observation_id, camera_id, camera_name, lat, lon, timestamp,
                 snapshot_count, crowd_density, step_free_access, visible_hazards,
                 platform_condition, mobility_impact, recommended_action, confidence, raw_insight)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    obs["observation_id"],
                    obs["camera_id"],
                    obs["camera_name"],
                    obs["lat"],
                    obs["lon"],
                    obs["timestamp"],
                    obs["snapshot_count"],
                    obs["crowd_density"],
                    obs["step_free_access"],
                    json.dumps(obs["visible_hazards"]),
                    obs["platform_condition"],
                    obs["mobility_impact"],
                    obs["recommended_action"],
                    obs["confidence"],
                    json.dumps(obs["raw_insight"]),
                ),
            )
        conn.commit()

    # 8. Rebuild GeoJSON
    _rebuild_observation_geojson()

    return observations


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _ensure_observation_table() -> None:
    LIVE_FEED_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(LIVE_FEED_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS live_observations (
                observation_id TEXT PRIMARY KEY,
                camera_id TEXT,
                camera_name TEXT,
                lat REAL,
                lon REAL,
                timestamp TEXT,
                snapshot_count INTEGER,
                crowd_density TEXT,
                step_free_access TEXT,
                visible_hazards TEXT,
                platform_condition TEXT,
                mobility_impact TEXT,
                recommended_action TEXT,
                confidence REAL,
                raw_insight TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_lo_camera ON live_observations(camera_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_lo_timestamp ON live_observations(timestamp)"
        )
        conn.commit()


def _rebuild_observation_geojson() -> None:
    features: list[dict] = []
    if not LIVE_FEED_DB.exists():
        return
    with sqlite3.connect(LIVE_FEED_DB) as conn:
        conn.row_factory = sqlite3.Row
        # Get latest observation per camera
        rows = conn.execute(
            """
            SELECT * FROM live_observations
            WHERE timestamp = (
                SELECT MAX(timestamp) FROM live_observations AS sub
                WHERE sub.camera_id = live_observations.camera_id
            )
            ORDER BY timestamp DESC
            """
        ).fetchall()
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
                    "observation_id": row["observation_id"],
                    "camera_id": row["camera_id"],
                    "camera_name": row["camera_name"],
                    "crowd_density": row["crowd_density"],
                    "step_free_access": row["step_free_access"],
                    "visible_hazards": row["visible_hazards"],
                    "platform_condition": row["platform_condition"],
                    "mobility_impact": row["mobility_impact"],
                    "recommended_action": row["recommended_action"],
                    "confidence": row["confidence"],
                    "timestamp": row["timestamp"],
                },
            }
            features.append(feature)

    geojson_path = REPO_ROOT / "data" / "geo" / "live_observations.geojson"
    geojson_path.parent.mkdir(parents=True, exist_ok=True)
    with geojson_path.open("w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, indent=2)


# ---------------------------------------------------------------------------
# Query interface
# ---------------------------------------------------------------------------

def get_latest_observations(camera_id: str | None = None, limit: int = 50) -> list[dict]:
    """Get latest live feed observations."""
    if not LIVE_FEED_DB.exists():
        return []
    with sqlite3.connect(LIVE_FEED_DB) as conn:
        conn.row_factory = sqlite3.Row
        if camera_id:
            rows = conn.execute(
                "SELECT * FROM live_observations WHERE camera_id = ? ORDER BY timestamp DESC LIMIT ?",
                (camera_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM live_observations ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def get_critical_observations(min_confidence: float = 0.6) -> list[dict]:
    """Get observations with high mobility impact or crowd density."""
    if not LIVE_FEED_DB.exists():
        return []
    with sqlite3.connect(LIVE_FEED_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM live_observations
            WHERE (mobility_impact IN ('moderate', 'severe')
                   OR crowd_density IN ('high', 'critical')
                   OR step_free_access IN ('partially_blocked', 'fully_blocked'))
              AND confidence >= ?
            ORDER BY timestamp DESC LIMIT 100
            """,
            (min_confidence,),
        ).fetchall()
        return [dict(r) for r in rows]
