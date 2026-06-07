"""User preferences store (web session + optional USER.md sync)."""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass
class UserPreferences:
    tube_lines: list[str] = field(default_factory=list)
    areas: list[str] = field(default_factory=list)
    ev_enabled: bool = False
    commute_morning: str = "07:00-09:30"
    commute_evening: str = "17:00-19:30"
    onboarding_complete: bool = False

    def to_dict(self) -> dict:
        return {
            "tube_lines": self.tube_lines,
            "areas": self.areas,
            "ev_enabled": self.ev_enabled,
            "commute_morning": self.commute_morning,
            "commute_evening": self.commute_evening,
            "onboarding_complete": self.onboarding_complete,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> UserPreferences:
        if not data:
            return cls()
        return cls(
            tube_lines=list(data.get("tube_lines") or []),
            areas=list(data.get("areas") or []),
            ev_enabled=bool(data.get("ev_enabled")),
            commute_morning=str(data.get("commute_morning") or "07:00-09:30"),
            commute_evening=str(data.get("commute_evening") or "17:00-19:30"),
            onboarding_complete=bool(data.get("onboarding_complete")),
        )


class PersonalizationStore:
    def __init__(self, db_path: Path, *, user_md_path: Path | None = None) -> None:
        self._path = db_path
        self._user_md = user_md_path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS web_preferences (
                    session_id TEXT PRIMARY KEY,
                    prefs_json TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )

    def get(self, session_id: str) -> UserPreferences:
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT prefs_json FROM web_preferences WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return UserPreferences()
        try:
            return UserPreferences.from_dict(json.loads(row["prefs_json"]))
        except json.JSONDecodeError:
            return UserPreferences()

    def save(self, session_id: str, prefs: UserPreferences) -> UserPreferences:
        import time

        payload = json.dumps(prefs.to_dict())
        with self._lock, self._conn() as conn:
            conn.execute(
                """
                INSERT INTO web_preferences (session_id, prefs_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    prefs_json = excluded.prefs_json,
                    updated_at = excluded.updated_at
                """,
                (session_id, payload, int(time.time() * 1000)),
            )
        if self._user_md and prefs.onboarding_complete:
            self._sync_user_md(prefs)
        return prefs

    def _sync_user_md(self, prefs: UserPreferences) -> None:
        if not self._user_md or not self._user_md.parent.exists():
            return
        path = self._user_md
        text = path.read_text(encoding="utf-8") if path.exists() else ""

        lines_yaml = "\n".join(f'  - "{line}"' for line in prefs.tube_lines) or '  - "central"'
        areas_yaml = "\n".join(
            f'    - label: "{a}"\n      ward_or_postcode_prefix: "{a}"' for a in prefs.areas
        ) or '    - label: "home"\n      ward_or_postcode_prefix: "E15"'

        transport_block = f"""```yaml
transport:
  usual_lines: [{", ".join(repr(l) for l in prefs.tube_lines) or '"central"'}]
  areas:
{areas_yaml}
  alert_on:
    line_disruption: true
    road_congestion_on_commute: true
```"""

        ev_block = f"""```yaml
ev:
  enabled: {str(prefs.ev_enabled).lower()}
  min_availability_ratio: 0.25
  areas:
{areas_yaml}
```"""

        activity_block = f"""```yaml
activity:
  morning_commute_window: "{prefs.commute_morning}"
  evening_commute_window: "{prefs.commute_evening}"
```"""

        for label, block in (
            ("transport", transport_block),
            ("ev", ev_block),
            ("activity", activity_block),
        ):
            pattern = rf"##[^\n]*\n\n```yaml\n{label}:.*?\n```"
            section = f"## {label.title()} (synced from web onboarding)\n\n{block}"
            if re.search(pattern, text, re.DOTALL):
                text = re.sub(pattern, section.split("\n", 1)[1], text, count=1, flags=re.DOTALL)
            elif label == "transport":
                text = text.rstrip() + "\n\n" + section + "\n"

        path.write_text(text, encoding="utf-8")

