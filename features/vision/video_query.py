"""Natural language query engine over video events.

Uses Nemotron (via OpenAI-compatible API) to convert natural language
questions into structured SQL queries over the video event database.

Examples:
    "Show flooding events longer than 5 seconds near Camden"
    "When did the pavement obstruction at Bank first appear?"
    "List all broken lift detections from yesterday"
    "Which video had the most persistent hazard?"

Different from Argus:
- Argus: operator asks about traffic counts → SQL-like queries on vehicle data
- This: operator asks about *accessibility hazard timelines* → semantic parsing
       → temporal event retrieval with natural language
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from features.vision.video_pipeline import VIDEO_DB

NEMOTRON_URL = os.getenv("NEMOTRON_URL", "http://localhost:8008/v1")


# ---------------------------------------------------------------------------
# NL → SQL via Nemotron
# ---------------------------------------------------------------------------

_SQL_SCHEMA = """
Table: video_events
Columns:
  event_id TEXT PRIMARY KEY
  video_id TEXT
  category TEXT -- one of: pavement_obstruction, broken_lift, missing_dropped_kerb,
                 --          flooding, illegal_parking, broken_ev_charger,
                 --          missing_tactile_paving, unknown
  label TEXT    -- raw open-vocab label from LocateAnything
  start_frame INTEGER
  end_frame INTEGER
  duration_sec REAL
  avg_confidence REAL
  frame_count INTEGER
  bbox_history TEXT  -- JSON array of bboxes
  lat REAL
  lon REAL
  ward TEXT
  borough TEXT
  timestamp TEXT  -- ISO 8601 when the event was persisted
  video_path TEXT
"""


def nl_to_sql(question: str) -> str:
    """Use Nemotron to translate a natural language question into a SQLite query.

    Args:
        question: User's natural language question.

    Returns:
        A valid SQLite SELECT query string, or simple fallback query on parse failure.
    """
    system_prompt = (
        "You are a SQLite query generator for a video hazard event database.\n"
        "Given a natural language question, output ONLY a valid SQLite SELECT query.\n"
        "Do NOT include markdown fences, explanations, or comments.\n"
        "Use the following schema:\n" + _SQL_SCHEMA
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Question: {question}\n\nSQL:"},
    ]

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{NEMOTRON_URL}/chat/completions",
                json={
                    "model": "nemotron-omni",
                    "messages": messages,
                    "max_tokens": 256,
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            sql = data["choices"][0]["message"]["content"].strip()
            # Safety: only allow SELECT queries
            if not sql.upper().startswith("SELECT"):
                return _fallback_sql(question)
            return sql
    except Exception:
        return _fallback_sql(question)


def _fallback_sql(question: str) -> str:
    """Heuristic fallback when Nemotron NL→SQL fails."""
    q = question.lower()

    # Extract category hints
    category_map = {
        "pavement": "pavement_obstruction",
        "sidewalk": "pavement_obstruction",
        "lift": "broken_lift",
        "elevator": "broken_lift",
        "kerb": "missing_dropped_kerb",
        "curb": "missing_dropped_kerb",
        "flood": "flooding",
        "water": "flooding",
        "parking": "illegal_parking",
        "charger": "broken_ev_charger",
        "tactile": "missing_tactile_paving",
    }
    category = None
    for kw, cat in category_map.items():
        if kw in q:
            category = cat
            break

    # Build WHERE clause
    conditions = []
    params: list[str] = []
    if category:
        conditions.append(f"category = '{category}'")

    if "longer than" in q or "more than" in q:
        # Try to extract number
        import re
        nums = re.findall(r"(\d+(?:\.\d+)?)\s*seconds?", q)
        if not nums:
            nums = re.findall(r"(\d+(?:\.\d+)?)\s*secs?", q)
        if nums:
            conditions.append(f"duration_sec >= {nums[0]}")

    if "yesterday" in q:
        yesterday = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")
        conditions.append(f"timestamp LIKE '{yesterday}%'")

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    return f"SELECT * FROM video_events WHERE {where_clause} ORDER BY timestamp DESC LIMIT 50"


# ---------------------------------------------------------------------------
# Execute query
# ---------------------------------------------------------------------------

def query_events(question: str) -> dict[str, Any]:
    """Answer a natural language question about video events.

    Returns:
        Dict with generated_sql, results (list of event dicts), and result_count.
    """
    if not VIDEO_DB.exists():
        return {"sql": "", "results": [], "result_count": 0, "error": "No video events database"}

    sql = nl_to_sql(question)

    try:
        with sqlite3.connect(VIDEO_DB) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql).fetchall()
            results = [dict(r) for r in rows]
            return {
                "sql": sql,
                "results": results,
                "result_count": len(results),
            }
    except Exception as exc:
        return {
            "sql": sql,
            "results": [],
            "result_count": 0,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Semantic search over event labels (no GPU vector DB needed)
# ---------------------------------------------------------------------------

def semantic_event_search(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Simple keyword + fuzzy match over event labels and categories.

    Lightweight alternative to full vector search. Uses Nemotron for
    query expansion if available, falls back to SQL LIKE.
    """
    if not VIDEO_DB.exists():
        return []

    # Expand query with synonyms
    expanded = _expand_query(query)
    like_patterns = [f"%{w}%" for w in expanded]

    with sqlite3.connect(VIDEO_DB) as conn:
        conn.row_factory = sqlite3.Row
        all_results: list[dict] = []
        for pattern in like_patterns:
            rows = conn.execute(
                "SELECT * FROM video_events WHERE label LIKE ? OR category LIKE ? OR borough LIKE ? OR ward LIKE ? ORDER BY timestamp DESC LIMIT ?",
                (pattern, pattern, pattern, pattern, limit),
            ).fetchall()
            for r in rows:
                d = dict(r)
                if d not in all_results:
                    all_results.append(d)
        return all_results[:limit]


def _expand_query(query: str) -> list[str]:
    """Expand query with hazard taxonomy synonyms."""
    q = query.lower()
    words = [w.strip(".,!?;:") for w in q.split()]

    # Add canonical terms if slang/synonyms detected
    synonym_map = {
        "pavement": ["pavement", "sidewalk", "path"],
        "sidewalk": ["pavement", "sidewalk", "path"],
        "lift": ["lift", "elevator"],
        "elevator": ["lift", "elevator"],
        "kerb": ["kerb", "curb"],
        "curb": ["kerb", "curb"],
        "flood": ["flood", "flooding", "water"],
        "water": ["flood", "flooding", "water"],
        "parking": ["parking", "parked", "vehicle"],
        "charger": ["charger", "charging", "ev"],
        "tactile": ["tactile", "paving"],
    }

    expanded = set(words)
    for w in words:
        if w in synonym_map:
            expanded.update(synonym_map[w])
    return list(expanded)
