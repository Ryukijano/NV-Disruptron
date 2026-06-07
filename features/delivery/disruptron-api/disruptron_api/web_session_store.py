from __future__ import annotations

import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator


def _now_ms() -> int:
    return int(datetime.now(UTC).timestamp() * 1000)


@dataclass(frozen=True, slots=True)
class WebSummary:
    date: str
    title: str
    body: str
    updated_at: int


@dataclass(frozen=True, slots=True)
class WebNotification:
    id: str
    title: str
    body: str
    kind: str
    timestamp: int


class WebSessionStore:
    """Per-session summaries and notifications (SQLite). Chat lives in context_store."""

    def __init__(self, path: Path) -> None:
        self._path = path
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
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS web_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'web-user',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS web_summaries (
                    session_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    updated_at INTEGER NOT NULL,
                    PRIMARY KEY (session_id, date),
                    FOREIGN KEY (session_id) REFERENCES web_sessions(session_id)
                );
                CREATE TABLE IF NOT EXISTS web_notifications (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'alert',
                    timestamp INTEGER NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES web_sessions(session_id)
                );
                CREATE INDEX IF NOT EXISTS idx_web_notifications_session
                    ON web_notifications(session_id, timestamp DESC);
                """
            )

    def ensure_session(self, session_id: str | None, *, user_id: str = "web-user") -> str:
        sid = session_id.strip() if session_id and session_id.strip() else f"web-{uuid.uuid4().hex[:12]}"
        now = _now_ms()
        with self._lock:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT session_id FROM web_sessions WHERE session_id = ?", (sid,)
                ).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO web_sessions (session_id, user_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
                        (sid, user_id, now, now),
                    )
                else:
                    conn.execute(
                        "UPDATE web_sessions SET updated_at = ? WHERE session_id = ?",
                        (now, sid),
                    )
        return sid

    def list_summaries(self, session_id: str, *, limit: int = 60) -> list[WebSummary]:
        with self._lock:
            with self._conn() as conn:
                rows = conn.execute(
                    """
                    SELECT date, title, body, updated_at FROM web_summaries
                    WHERE session_id = ? ORDER BY date DESC LIMIT ?
                    """,
                    (session_id, limit),
                ).fetchall()
        return [
            WebSummary(
                date=str(r["date"]),
                title=str(r["title"]),
                body=str(r["body"]),
                updated_at=int(r["updated_at"]),
            )
            for r in rows
        ]

    def upsert_summary(
        self, session_id: str, *, date: str, title: str, body: str
    ) -> WebSummary:
        self.ensure_session(session_id)
        now = _now_ms()
        with self._lock:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT INTO web_summaries (session_id, date, title, body, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(session_id, date) DO UPDATE SET
                        title = excluded.title,
                        body = excluded.body,
                        updated_at = excluded.updated_at
                    """,
                    (session_id, date, title, body, now),
                )
        return WebSummary(date=date, title=title, body=body, updated_at=now)

    def list_notifications(self, session_id: str, *, limit: int = 100) -> list[WebNotification]:
        with self._lock:
            with self._conn() as conn:
                rows = conn.execute(
                    """
                    SELECT id, title, body, kind, timestamp FROM web_notifications
                    WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?
                    """,
                    (session_id, limit),
                ).fetchall()
        return [
            WebNotification(
                id=str(r["id"]),
                title=str(r["title"]),
                body=str(r["body"]),
                kind=str(r["kind"]),
                timestamp=int(r["timestamp"]),
            )
            for r in rows
        ]

    def add_notification(
        self,
        session_id: str,
        *,
        title: str,
        body: str = "",
        kind: str = "alert",
        notification_id: str | None = None,
    ) -> WebNotification:
        self.ensure_session(session_id)
        nid = notification_id or f"ntf-{uuid.uuid4().hex}"
        ts = _now_ms()
        with self._lock:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO web_notifications
                    (id, session_id, title, body, kind, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (nid, session_id, title, body, kind, ts),
                )
                count = conn.execute(
                    "SELECT COUNT(*) AS c FROM web_notifications WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                excess = int(count["c"]) - 100
                if excess > 0:
                    conn.execute(
                        """
                        DELETE FROM web_notifications WHERE id IN (
                            SELECT id FROM web_notifications
                            WHERE session_id = ?
                            ORDER BY timestamp ASC LIMIT ?
                        )
                        """,
                        (session_id, excess),
                    )
        return WebNotification(id=nid, title=title, body=body, kind=kind, timestamp=ts)
