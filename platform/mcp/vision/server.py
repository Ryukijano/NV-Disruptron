"""Vision MCP Server for NV-Disruptron.

Exposes LocateAnything-3B / Nemotron grounding and hazard pipeline to agents.
"""

from __future__ import annotations

import base64
import io
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from features.vision.hazard_pipeline import (  # noqa: E402
    analyze_street_image,
    list_hazard_hotspots,
    report_hazard,
)
from features.vision.video_pipeline import (  # noqa: E402
    analyze_video,
    get_event_timeline,
    list_video_events,
)
from features.vision.video_query import (  # noqa: E402
    query_events,
)
from features.vision.live_feed_pipeline import (  # noqa: E402
    run_live_feed_cycle,
    get_latest_observations,
    get_critical_observations,
)
from features.vision.audio_pipeline import (  # noqa: E402
    analyze_audio,
    list_audio_observations,
    get_high_priority_audio,
)

mcp = FastMCP(
    "NV-Disruptron Vision",
    instructions=(
        "Vision-language grounding for street-image and VIDEO hazard detection. "
        "Uses LocateAnything-3B (primary) or Nemotron Omni grounding (fallback). "
        "Hazard categories: pavement_obstruction, broken_lift, missing_dropped_kerb, "
        "flooding, illegal_parking, broken_ev_charger, missing_tactile_paving. "
        "Video pipeline: temporal tracking of persistent hazards across frames, "
        "not per-frame noise. Supports natural language queries over video events."
    ),
)


@mcp.tool()
async def analyze_street_image_tool(
    image_path: str,
    lat: float | None = None,
    lon: float | None = None,
    confidence_threshold: float = 0.3,
) -> list[dict]:
    """Analyze a street image for accessibility hazards.

    Args:
        image_path: Absolute path to image file on disk.
        lat: Optional explicit latitude (overrides EXIF GPS).
        lon: Optional explicit longitude (overrides EXIF GPS).
        confidence_threshold: Min confidence 0–1 (default 0.3).

    Returns:
        List of hazard records with category, confidence, lat/lon, ward, bbox.
    """
    records = await analyze_street_image(image_path, lat, lon, confidence_threshold)
    return [asdict_safe(r) for r in records]


@mcp.tool()
async def report_hazard_tool(records: list[dict], user_id: str = "anonymous") -> dict:
    """Persist detected hazards to database and regenerate GeoJSON map layer.

    Args:
        records: Hazard records from analyze_street_image_tool.
        user_id: Reporter ID (default anonymous for privacy).

    Returns:
        Summary with persisted_count, total_records, sqlite_path, geojson_path.
    """
    from features.vision.hazard_pipeline import HazardRecord

    hazard_records = [HazardRecord(**r) for r in records]
    return await report_hazard(hazard_records, user_id)


@mcp.tool()
def list_hazard_hotspots_tool(
    category: str | None = None,
    borough: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Query persisted hazard records for map display.

    Args:
        category: Optional filter (e.g. 'pavement_obstruction', 'broken_lift').
        borough: Optional borough name filter.
        limit: Max records (default 50).
    """
    return list_hazard_hotspots(category, borough, limit)


@mcp.tool()
def get_vision_system_status() -> dict:
    """Health check for vision pipeline."""
    from features.vision.locate_anything_client import get_client

    client = get_client()
    return {
        "locate_anything_available": client.is_available(),
        "fallback_to_nemotron": client.fallback,
        "hazard_taxonomy": list({
            "pavement_obstruction", "broken_lift", "missing_dropped_kerb",
            "flooding", "illegal_parking", "broken_ev_charger", "missing_tactile_paving",
        }),
    }


# ---------------------------------------------------------------------------
# Video tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def analyze_video_tool(
    video_path: str,
    lat: float | None = None,
    lon: float | None = None,
    target_fps: float = 0.5,
    confidence_threshold: float = 0.3,
    min_event_duration_sec: float = 1.0,
) -> dict:
    """Analyze a video for persistent accessibility hazards using LocateAnything-3B temporal tracking.

    Different from Argus per-frame YOLO: this tracks objects across time to detect
    *persistent* hazards (e.g. a blocked pavement that lasts 10 seconds) rather than
    per-frame noise.

    Args:
        video_path: Absolute path to video file.
        lat: Optional latitude for geotagging.
        lon: Optional longitude for geotagging.
        target_fps: Frame sampling rate (default 0.5 = one frame every 2 seconds).
        confidence_threshold: Min detection confidence.
        min_event_duration_sec: Ignore events shorter than this (filters flicker).

    Returns:
        Summary with video_id, persistent event count, categories, and storage paths.
    """
    return await analyze_video(
        video_path=video_path,
        lat=lat,
        lon=lon,
        target_fps=target_fps,
        confidence_threshold=confidence_threshold,
        min_event_duration_sec=min_event_duration_sec,
    )


@mcp.tool()
def list_video_events_tool(
    category: str | None = None,
    borough: str | None = None,
    min_duration_sec: float | None = None,
    limit: int = 100,
) -> list[dict]:
    """Query persisted video hazard events.

    Args:
        category: Filter by hazard category (e.g. 'flooding', 'broken_lift').
        borough: Filter by London borough name.
        min_duration_sec: Only events lasting at least this long.
        limit: Max results.
    """
    return list_video_events(category, borough, min_duration_sec, limit)


@mcp.tool()
def get_video_timeline_tool(video_id: str) -> list[dict]:
    """Get chronological event timeline for a specific video.

    Args:
        video_id: Video ID returned by analyze_video_tool.
    """
    return get_event_timeline(video_id)


@mcp.tool()
def query_video_events_tool(question: str) -> dict:
    """Ask a natural language question about video events.

    Uses Nemotron to translate the question into a SQL query over the
    video event database.

    Examples:
        - "Show flooding events longer than 5 seconds"
        - "When did the pavement obstruction at Bank first appear?"
        - "List all broken lift detections from yesterday"

    Args:
        question: Natural language question.

    Returns:
        Dict with generated SQL, results, and result count.
    """
    return query_events(question)


@mcp.tool()
async def run_live_feed_cycle_tool(
    camera_ids: list[str] | None = None,
    snapshots_per_camera: int = 3,
    snapshot_delay_sec: float = 5.0,
) -> list[dict]:
    """Run one live feed monitoring cycle on TfL JamCams using Nemotron Omni reasoning.

    Different from Argus per-frame YOLO: this uses Nemotron Omni's multimodal
    reasoning to analyze accessibility and mobility conditions from CCTV snapshots.

    Args:
        camera_ids: Specific JamCam IDs (e.g. ['JamCam_001']). Auto-selects if None.
        snapshots_per_camera: How many snapshots to collect per camera.
        snapshot_delay_sec: Delay between snapshots for temporal context.

    Returns:
        List of observation records with crowd_density, step_free_access, hazards.
    """
    return await run_live_feed_cycle(
        camera_ids=camera_ids,
        snapshots_per_camera=snapshots_per_camera,
        snapshot_delay_sec=snapshot_delay_sec,
    )


@mcp.tool()
def get_latest_observations_tool(camera_id: str | None = None, limit: int = 50) -> list[dict]:
    """Get latest live feed observations from TfL JamCam monitoring."""
    return get_latest_observations(camera_id, limit)


@mcp.tool()
def get_critical_observations_tool(min_confidence: float = 0.6) -> list[dict]:
    """Get observations with high mobility impact or crowd density.

    Filters to observations where:
      - mobility_impact is 'moderate' or 'severe', OR
      - crowd_density is 'high' or 'critical', OR
      - step_free_access is 'partially_blocked' or 'fully_blocked'
    """
    return get_critical_observations(min_confidence)


@mcp.tool()
async def analyze_audio_tool(
    audio_path: str,
    lat: float | None = None,
    lon: float | None = None,
    context_hint: str = "",
) -> dict:
    """Analyze environmental audio with Nemotron Omni for accessibility insights.

    Nemotron Omni accepts native audio input (not just transcripts) and can
    reason about crowd noise, sirens, announcements, construction sounds, etc.

    Args:
        audio_path: Path to audio file (wav, mp3, ogg, flac).
        lat: Optional geotag latitude.
        lon: Optional geotag longitude.
        context_hint: Optional context like 'TfL station platform'.

    Returns:
        Structured audio scene analysis (crowd level, sounds, incidents).
    """
    from pathlib import Path
    path = Path(audio_path)
    audio_format = path.suffix.lstrip(".").lower() or "wav"
    audio_bytes = path.read_bytes()
    return await analyze_audio(
        audio_bytes=audio_bytes,
        audio_format=audio_format,
        lat=lat,
        lon=lon,
        source="mcp_tool",
        context_hint=context_hint,
    )


@mcp.tool()
def list_audio_observations_tool(limit: int = 50) -> list[dict]:
    """List recent audio observations from the database."""
    return list_audio_observations(limit=limit)


@mcp.tool()
def get_high_priority_audio_tool() -> list[dict]:
    """Get high-priority audio observations (incidents, high relevance)."""
    return get_high_priority_audio()


def asdict_safe(obj: Any) -> dict:
    """Convert dataclass to dict, handling nested dataclasses."""
    from dataclasses import asdict, is_dataclass

    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)  # type: ignore[arg-type]
    if isinstance(obj, list):
        return [asdict_safe(i) for i in obj]  # type: ignore[return-value]
    return obj  # type: ignore[return-value]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
