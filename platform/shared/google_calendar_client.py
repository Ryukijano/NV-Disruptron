"""Google Calendar API client — shares OAuth with @cocal/google-calendar-mcp."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
CALENDAR_API = "https://www.googleapis.com/calendar/v3"


def credentials_path() -> Path:
    env = os.getenv("GOOGLE_OAUTH_CREDENTIALS")
    if env:
        return Path(env).expanduser().resolve()
    return ROOT / "gcp-oauth.keys.json"


def token_path() -> Path:
    env = os.getenv("GOOGLE_CALENDAR_MCP_TOKEN_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / ".config" / "google-calendar-mcp" / "tokens.json"


def _load_oauth_keys() -> dict[str, str]:
    path = credentials_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"Google OAuth keys not found at {path}. "
            "See platform/delivery/docs/GOOGLE_CALENDAR.md"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    installed = data.get("installed") or data
    return {
        "client_id": installed["client_id"],
        "client_secret": installed["client_secret"],
        "token_uri": installed.get("token_uri", "https://oauth2.googleapis.com/token"),
    }


def _pick_account_tokens(store: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("normal", "default", "primary"):
        if key in store and isinstance(store[key], dict) and store[key].get("access_token"):
            return store[key]
    for value in store.values():
        if isinstance(value, dict) and value.get("access_token"):
            return value
    return None


def _load_stored_tokens() -> dict[str, Any] | None:
    path = token_path()
    if not path.is_file():
        return None
    store = json.loads(path.read_text(encoding="utf-8"))
    if "access_token" in store:
        return store
    return _pick_account_tokens(store)


def connection_status() -> dict[str, Any]:
    """Report whether Calendar API credentials and tokens are present."""
    keys = credentials_path()
    tokens = token_path()
    has_keys = keys.is_file()
    has_tokens = tokens.is_file() and _load_stored_tokens() is not None
    return {
        "credentials_path": str(keys),
        "credentials_present": has_keys,
        "token_path": str(tokens),
        "token_present": has_tokens,
        "connected": has_keys and has_tokens,
    }


def _get_credentials():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    keys = _load_oauth_keys()
    tokens = _load_stored_tokens()
    if not tokens:
        raise RuntimeError(
            "Google Calendar not authenticated. Run: "
            "./scripts/setup_google_calendar.sh"
        )

    creds = Credentials(
        token=tokens.get("access_token"),
        refresh_token=tokens.get("refresh_token"),
        token_uri=keys["token_uri"],
        client_id=keys["client_id"],
        client_secret=keys["client_secret"],
        scopes=tokens.get("scope", " ").split() or SCOPES,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def _calendar_service():
    from googleapiclient.discovery import build

    return build("calendar", "v3", credentials=_get_credentials(), cache_discovery=False)


def list_upcoming_events(
    *,
    calendar_id: str = "primary",
    max_results: int = 10,
    time_min: datetime | None = None,
) -> list[dict[str, Any]]:
    service = _calendar_service()
    start = time_min or datetime.now(UTC)
    result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=start.isoformat(),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = result.get("items", [])
    return [
        {
            "id": e.get("id"),
            "summary": e.get("summary"),
            "start": (e.get("start") or {}).get("dateTime") or (e.get("start") or {}).get("date"),
            "end": (e.get("end") or {}).get("dateTime") or (e.get("end") or {}).get("date"),
            "location": e.get("location"),
            "html_link": e.get("htmlLink"),
        }
        for e in events
    ]


def create_event(
    *,
    summary: str,
    description: str | None = None,
    calendar_id: str = "primary",
    start: datetime | None = None,
    duration_minutes: int = 30,
) -> dict[str, Any]:
    service = _calendar_service()
    start_dt = start or datetime.now(UTC)
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    body: dict[str, Any] = {
        "summary": summary,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Europe/London"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Europe/London"},
    }
    if description:
        body["description"] = description

    created = service.events().insert(calendarId=calendar_id, body=body).execute()
    return {
        "id": created.get("id"),
        "summary": created.get("summary"),
        "html_link": created.get("htmlLink"),
        "start": (created.get("start") or {}).get("dateTime"),
    }
