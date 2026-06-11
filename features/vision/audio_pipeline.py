"""Audio ingestion pipeline for Nemotron Omni multimodal reasoning.

Nemotron 3 Nano Omni supports native audio input (not just text transcripts).
This pipeline records/uploads audio, sends it to Nemotron for scene/environmental
understanding, and persists structured observations.

Use cases:
  - Environmental sound analysis (crowd noise, sirens, construction)
  - Accessibility context (announcements, distress sounds)
  - Incident detection from audio cues
"""

from __future__ import annotations

import base64
import json
import os
import sqlite3
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

NEMOTRON_URL = os.getenv("NEMOTRON_URL", "http://localhost:8008/v1")

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIO_DB = REPO_ROOT / "data" / "audio_observations.db"


# ---------------------------------------------------------------------------
# Audio analysis with Nemotron Omni
# ---------------------------------------------------------------------------

async def analyze_audio(
    audio_bytes: bytes,
    audio_format: str = "wav",
    lat: float | None = None,
    lon: float | None = None,
    source: str = "upload",
    context_hint: str = "",
) -> dict[str, Any]:
    """Send audio to Nemotron Omni for environmental/accessibility scene understanding.

    Args:
        audio_bytes: Raw audio file bytes.
        audio_format: Audio format (wav, mp3, ogg, flac).
        lat: Optional geotag latitude.
        lon: Optional geotag longitude.
        source: 'upload', 'live_recording', 'station_feed', etc.
        context_hint: Optional context string (e.g. 'TfL station platform').

    Returns:
        Structured observation dict with audio scene analysis.
    """
    audio_b64 = base64.b64encode(audio_bytes).decode()

    prompt = (
        "You are an AI accessibility monitor analyzing environmental audio.\n"
        "Listen to this audio clip and analyze the acoustic environment for\n"
        "mobility and accessibility conditions in a public transit context.\n\n"
    )
    if context_hint:
        prompt += f"Context: {context_hint}\n\n"

    prompt += (
        "Provide a structured JSON response with these exact fields:\n"
        "{\n"
        '  "soundscape_type": "traffic|crowd|announcement|construction|alarm|nature|quiet|other",\n'
        '  "crowd_level": "none|low|moderate|high|critical",\n'
        '  "detected_sounds": ["list of specific sounds like siren, drilling, footsteps, announcement"],\n'
        '  "accessibility_relevance": "none|low|moderate|high",\n'
        '  "incident_indicators": ["none"] or list like ["distress", "alarm", "construction_noise"],\n'
        '  "environment_assessment": "brief description of the acoustic environment",\n'
        '  "recommended_action": "brief recommendation for travelers based on audio cues",\n'
        '  "confidence": 0.0 to 1.0\n'
        "}\n\n"
        "Be precise and evidence-based. If you cannot determine something, use 'unknown'."
    )

    messages = [
        {"role": "system", "content": "You are a multimodal accessibility analyst. Respond only in valid JSON."},
        {
            "role": "user",
            "content": [
                {"type": "input_audio", "input_audio": {"data": audio_b64, "format": audio_format}},
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
            insight = _extract_json(content)
    except Exception as exc:
        print(f"Nemotron audio analysis failed: {exc}")
        insight = {
            "soundscape_type": "unknown",
            "crowd_level": "unknown",
            "detected_sounds": ["analysis_failed"],
            "accessibility_relevance": "unknown",
            "incident_indicators": ["analysis_failed"],
            "environment_assessment": "Analysis failed.",
            "recommended_action": "",
            "confidence": 0.0,
            "error": str(exc),
        }

    observation = {
        "observation_id": f"audio-{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.now(UTC).isoformat(),
        "lat": lat,
        "lon": lon,
        "source": source,
        "audio_format": audio_format,
        **insight,
    }

    _persist_observation(observation)
    return observation


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
# Persistence
# ---------------------------------------------------------------------------

def _ensure_table() -> None:
    AUDIO_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(AUDIO_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audio_observations (
                observation_id TEXT PRIMARY KEY,
                timestamp TEXT,
                lat REAL,
                lon REAL,
                source TEXT,
                audio_format TEXT,
                soundscape_type TEXT,
                crowd_level TEXT,
                detected_sounds TEXT,
                accessibility_relevance TEXT,
                incident_indicators TEXT,
                environment_assessment TEXT,
                recommended_action TEXT,
                confidence REAL,
                raw_response TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ao_timestamp ON audio_observations(timestamp)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ao_relevance ON audio_observations(accessibility_relevance)"
        )
        conn.commit()


def _persist_observation(obs: dict[str, Any]) -> None:
    _ensure_table()
    with sqlite3.connect(AUDIO_DB) as conn:
        conn.execute(
            """
            INSERT INTO audio_observations
            (observation_id, timestamp, lat, lon, source, audio_format,
             soundscape_type, crowd_level, detected_sounds, accessibility_relevance,
             incident_indicators, environment_assessment, recommended_action, confidence, raw_response)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                obs["observation_id"],
                obs["timestamp"],
                obs.get("lat"),
                obs.get("lon"),
                obs.get("source", "upload"),
                obs.get("audio_format", "wav"),
                obs.get("soundscape_type", "unknown"),
                obs.get("crowd_level", "unknown"),
                json.dumps(obs.get("detected_sounds", [])),
                obs.get("accessibility_relevance", "unknown"),
                json.dumps(obs.get("incident_indicators", [])),
                obs.get("environment_assessment", ""),
                obs.get("recommended_action", ""),
                obs.get("confidence", 0.0),
                json.dumps(obs.get("raw_response", "")),
            ),
        )
        conn.commit()
    _rebuild_geojson()


def _rebuild_geojson() -> None:
    if not AUDIO_DB.exists():
        return
    features: list[dict] = []
    with sqlite3.connect(AUDIO_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM audio_observations ORDER BY timestamp DESC LIMIT 500"
        ).fetchall()
        for row in rows:
            if row["lat"] is None or row["lon"] is None:
                continue
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [row["lon"], row["lat"]],
                },
                "properties": {
                    "observation_id": row["observation_id"],
                    "timestamp": row["timestamp"],
                    "soundscape_type": row["soundscape_type"],
                    "crowd_level": row["crowd_level"],
                    "detected_sounds": row["detected_sounds"],
                    "accessibility_relevance": row["accessibility_relevance"],
                    "incident_indicators": row["incident_indicators"],
                    "environment_assessment": row["environment_assessment"],
                    "recommended_action": row["recommended_action"],
                    "confidence": row["confidence"],
                },
            })

    geojson_path = REPO_ROOT / "data" / "geo" / "audio_observations.geojson"
    geojson_path.parent.mkdir(parents=True, exist_ok=True)
    with geojson_path.open("w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, indent=2)


# ---------------------------------------------------------------------------
# Query interface
# ---------------------------------------------------------------------------

def list_audio_observations(
    limit: int = 50,
    min_relevance: str | None = None,
) -> list[dict]:
    """Get latest audio observations, optionally filtered by relevance."""
    if not AUDIO_DB.exists():
        return []
    relevance_order = {"none": 0, "low": 1, "moderate": 2, "high": 3}
    with sqlite3.connect(AUDIO_DB) as conn:
        conn.row_factory = sqlite3.Row
        if min_relevance and min_relevance in relevance_order:
            min_val = relevance_order[min_relevance]
            allowed = [k for k, v in relevance_order.items() if v >= min_val]
            placeholders = ",".join("?" * len(allowed))
            rows = conn.execute(
                f"SELECT * FROM audio_observations WHERE accessibility_relevance IN ({placeholders}) ORDER BY timestamp DESC LIMIT ?",
                (*allowed, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM audio_observations ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def get_high_priority_audio() -> list[dict]:
    """Get high-priority audio observations (incidents, high relevance)."""
    if not AUDIO_DB.exists():
        return []
    with sqlite3.connect(AUDIO_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM audio_observations
            WHERE accessibility_relevance IN ('moderate', 'high')
               OR crowd_level IN ('high', 'critical')
               OR incident_indicators NOT LIKE '%"none"%'
            ORDER BY timestamp DESC LIMIT 100
            """
        ).fetchall()
        return [dict(r) for r in rows]
