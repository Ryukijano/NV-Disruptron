"""SQLite-backed conversation memory for NV-Disruptron (local-first)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "disruptron_context.db"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def conversation_id(channel: str, external_chat_id: str | int) -> str:
    return f"{channel.strip().lower()}:{external_chat_id}"


@dataclass(frozen=True, slots=True)
class Conversation:
    id: str
    channel: str
    external_chat_id: str
    session_key: str | None
    openclaw_session_id: str | None
    title: str | None
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class StoredMessage:
    id: int
    conversation_id: str
    run_id: str | None
    role: str
    content: str
    content_type: str
    media: dict[str, Any]
    input_tokens: int | None
    output_tokens: int | None
    created_at: str


class ContextStore:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    channel TEXT NOT NULL,
                    external_chat_id TEXT NOT NULL,
                    session_key TEXT,
                    openclaw_session_id TEXT,
                    title TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(channel, external_chat_id)
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    run_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_type TEXT NOT NULL DEFAULT 'text',
                    media_json TEXT NOT NULL DEFAULT '{}',
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_conv_created
                    ON messages(conversation_id, created_at);

                CREATE TABLE IF NOT EXISTS memory_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
                    scope TEXT NOT NULL DEFAULT 'global',
                    fact_key TEXT,
                    fact_text TEXT NOT NULL,
                    source_run_id TEXT,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_facts_scope_created
                    ON memory_facts(scope, created_at DESC);

                CREATE TABLE IF NOT EXISTS compaction_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    run_id TEXT,
                    summary TEXT NOT NULL,
                    tokens_before INTEGER,
                    created_at TEXT NOT NULL
                );
                """
            )

    def upsert_conversation(
        self,
        *,
        channel: str,
        external_chat_id: str | int,
        session_key: str | None = None,
        openclaw_session_id: str | None = None,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Conversation:
        cid = conversation_id(channel, external_chat_id)
        now = _utc_now()
        meta = json.dumps(metadata or {})
        with self._conn() as conn:
            row = conn.execute(
                "SELECT created_at FROM conversations WHERE id = ?", (cid,)
            ).fetchone()
            created = row["created_at"] if row else now
            conn.execute(
                """
                INSERT INTO conversations (
                    id, channel, external_chat_id, session_key, openclaw_session_id,
                    title, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    session_key = COALESCE(excluded.session_key, session_key),
                    openclaw_session_id = COALESCE(excluded.openclaw_session_id, openclaw_session_id),
                    title = COALESCE(excluded.title, title),
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    cid,
                    channel,
                    str(external_chat_id),
                    session_key,
                    openclaw_session_id,
                    title,
                    meta,
                    created,
                    now,
                ),
            )
        return self.get_conversation(cid)  # type: ignore[return-value]

    def get_conversation(self, cid: str) -> Conversation | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM conversations WHERE id = ?", (cid,)).fetchone()
        return self._row_to_conversation(row) if row else None

    def list_conversations(self, *, channel: str | None = None, limit: int = 50) -> list[Conversation]:
        query = "SELECT * FROM conversations"
        params: list[Any] = []
        if channel:
            query += " WHERE channel = ?"
            params.append(channel)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_conversation(r) for r in rows]

    def append_message(
        self,
        *,
        channel: str,
        external_chat_id: str | int,
        role: str,
        content: str,
        run_id: str | None = None,
        content_type: str = "text",
        media: dict[str, Any] | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        session_key: str | None = None,
        openclaw_session_id: str | None = None,
    ) -> StoredMessage:
        self.upsert_conversation(
            channel=channel,
            external_chat_id=external_chat_id,
            session_key=session_key,
            openclaw_session_id=openclaw_session_id,
        )
        cid = conversation_id(channel, external_chat_id)
        now = _utc_now()
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO messages (
                    conversation_id, run_id, role, content, content_type,
                    media_json, input_tokens, output_tokens, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cid,
                    run_id,
                    role,
                    content,
                    content_type,
                    json.dumps(media or {}),
                    input_tokens,
                    output_tokens,
                    now,
                ),
            )
            msg_id = int(cur.lastrowid)
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?", (now, cid)
            )
        return self.get_message(msg_id)  # type: ignore[return-value]

    def get_message(self, msg_id: int) -> StoredMessage | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (msg_id,)).fetchone()
        return self._row_to_message(row) if row else None

    def list_messages(
        self,
        cid: str,
        *,
        limit: int = 50,
        before_id: int | None = None,
    ) -> list[StoredMessage]:
        query = "SELECT * FROM messages WHERE conversation_id = ?"
        params: list[Any] = [cid]
        if before_id is not None:
            query += " AND id < ?"
            params.append(before_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_message(r) for r in reversed(rows)]

    def add_fact(
        self,
        *,
        fact_text: str,
        scope: str = "global",
        conversation_id: str | None = None,
        fact_key: str | None = None,
        source_run_id: str | None = None,
        tags: list[str] | None = None,
    ) -> int:
        now = _utc_now()
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO memory_facts (
                    conversation_id, scope, fact_key, fact_text, source_run_id, tags_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    scope,
                    fact_key,
                    fact_text,
                    source_run_id,
                    json.dumps(tags or []),
                    now,
                ),
            )
            return int(cur.lastrowid)

    def search_facts(
        self,
        query: str,
        *,
        scope: str | None = None,
        conversation_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        q = query.strip()
        if not q:
            sql = """
                SELECT id, conversation_id, scope, fact_key, fact_text, source_run_id, created_at
                FROM memory_facts WHERE 1=1
            """
            params: list[Any] = []
        else:
            like = f"%{q}%"
            sql = """
                SELECT id, conversation_id, scope, fact_key, fact_text, source_run_id, created_at
                FROM memory_facts
                WHERE (fact_text LIKE ? OR COALESCE(fact_key, '') LIKE ?)
            """
            params = [like, like]
        if scope:
            sql += " AND scope = ?"
            params.append(scope)
        if conversation_id:
            sql += " AND (conversation_id = ? OR scope = 'global')"
            params.append(conversation_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def add_compaction_summary(
        self,
        *,
        channel: str,
        external_chat_id: str | int,
        summary: str,
        run_id: str | None = None,
        tokens_before: int | None = None,
    ) -> int:
        cid = conversation_id(channel, external_chat_id)
        self.upsert_conversation(channel=channel, external_chat_id=external_chat_id)
        now = _utc_now()
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO compaction_summaries (
                    conversation_id, run_id, summary, tokens_before, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (cid, run_id, summary, tokens_before, now),
            )
            return int(cur.lastrowid)

    def latest_compaction(self, cid: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM compaction_summaries
                WHERE conversation_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (cid,),
            ).fetchone()
        return dict(row) if row else None

    def recall(
        self,
        *,
        channel: str,
        external_chat_id: str | int,
        max_chars: int = 2800,
        message_limit: int = 12,
        fact_limit: int = 8,
    ) -> dict[str, Any]:
        cid = conversation_id(channel, external_chat_id)
        conv = self.get_conversation(cid)
        messages = self.list_messages(cid, limit=message_limit) if conv else []
        compaction = self.latest_compaction(cid) if conv else None
        facts = self.search_facts("", conversation_id=cid, limit=fact_limit) if conv else []
        if not facts:
            with self._conn() as conn:
                rows = conn.execute(
                    """
                    SELECT id, conversation_id, scope, fact_key, fact_text, source_run_id, created_at
                    FROM memory_facts WHERE scope = 'global'
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (fact_limit,),
                ).fetchall()
            facts = [dict(r) for r in rows]

        lines: list[str] = ["# Recalled context (SQLite)"]
        if conv:
            lines.append(
                f"- conversation: `{conv.id}` session_key=`{conv.session_key or ''}` "
                f"openclaw=`{conv.openclaw_session_id or ''}`"
            )
        if compaction:
            lines.extend(["", "## Compaction summary", compaction["summary"][:800]])

        if facts:
            lines.extend(["", "## Memory facts"])
            for f in facts[:fact_limit]:
                key = f.get("fact_key") or "note"
                lines.append(f"- **{key}**: {f['fact_text'][:240]}")

        if messages:
            lines.extend(["", "## Recent messages"])
            for m in messages:
                snippet = m.content.replace("\n", " ")[:320]
                run = f" run={m.run_id}" if m.run_id else ""
                media = ""
                if m.media.get("image_ref"):
                    media = f" [image:{m.media['image_ref']}]"
                lines.append(f"- **{m.role}**{run}{media}: {snippet}")

        text = "\n".join(lines)
        if len(text) > max_chars:
            text = text[: max_chars - 20] + "\n… [truncated]"
        return {
            "conversation_id": cid,
            "found": conv is not None,
            "message_count": len(messages),
            "fact_count": len(facts),
            "recall_text": text,
        }

    def openclaw_session_id_for(self, channel: str, external_chat_id: str | int) -> str:
        """Stable OpenClaw session id for continuity across turns."""
        cid = conversation_id(channel, external_chat_id)
        conv = self.get_conversation(cid)
        if conv and conv.openclaw_session_id:
            return conv.openclaw_session_id
        sid = f"disruptron-{uuid.uuid4().hex[:16]}"
        self.upsert_conversation(
            channel=channel,
            external_chat_id=external_chat_id,
            openclaw_session_id=sid,
        )
        return sid

    def sync_openclaw_transcript(
        self,
        jsonl_path: Path,
        *,
        channel: str = "openclaw",
        external_chat_id: str | None = None,
        session_key: str | None = None,
    ) -> dict[str, Any]:
        """Import user/assistant text from an OpenClaw session JSONL file."""
        if not jsonl_path.exists():
            return {"ok": False, "error": f"missing {jsonl_path}"}

        imported = 0
        session_id = jsonl_path.stem.split("-topic-")[0]
        chat_id = external_chat_id or session_id
        self.upsert_conversation(
            channel=channel,
            external_chat_id=chat_id,
            openclaw_session_id=session_id,
            session_key=session_key or f"agent:disruptron:{chat_id}",
        )

        with jsonl_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                etype = entry.get("type")
                if etype == "compaction":
                    summary = entry.get("summary") or entry.get("text") or ""
                    if summary:
                        self.add_compaction_summary(
                            channel=channel,
                            external_chat_id=chat_id,
                            summary=summary,
                            tokens_before=entry.get("tokensBefore"),
                        )
                    continue
                if etype != "message":
                    continue
                msg = entry.get("message") or {}
                role = msg.get("role")
                if role not in {"user", "assistant"}:
                    continue
                content = _extract_message_text(msg)
                if not content:
                    continue
                media: dict[str, Any] = {}
                content_type = "text"
                for block in msg.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "image":
                        content_type = "image"
                        media["image_ref"] = block.get("url") or block.get("path") or "attached"
                self.append_message(
                    channel=channel,
                    external_chat_id=chat_id,
                    role=role,
                    content=content,
                    run_id=entry.get("id"),
                    content_type=content_type,
                    media=media,
                    openclaw_session_id=session_id,
                )
                imported += 1

        return {"ok": True, "imported": imported, "conversation_id": conversation_id(channel, chat_id)}

    @staticmethod
    def _row_to_conversation(row: sqlite3.Row) -> Conversation:
        return Conversation(
            id=row["id"],
            channel=row["channel"],
            external_chat_id=row["external_chat_id"],
            session_key=row["session_key"],
            openclaw_session_id=row["openclaw_session_id"],
            title=row["title"],
            metadata=json.loads(row["metadata_json"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> StoredMessage:
        return StoredMessage(
            id=row["id"],
            conversation_id=row["conversation_id"],
            run_id=row["run_id"],
            role=row["role"],
            content=row["content"],
            content_type=row["content_type"],
            media=json.loads(row["media_json"] or "{}"),
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            created_at=row["created_at"],
        )


def _extract_message_text(msg: dict[str, Any]) -> str:
    content = msg.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and block.get("text"):
                    parts.append(str(block["text"]))
                elif block.get("type") == "image":
                    parts.append("[image attached]")
        return "\n".join(parts).strip()
    return ""


def sync_all_openclaw_sessions(
    store: ContextStore,
    *,
    agent_id: str = "disruptron",
    sessions_dir: Path | None = None,
    sessions_json: Path | None = None,
) -> dict[str, Any]:
    base = sessions_dir or Path.home() / ".openclaw" / "agents" / agent_id / "sessions"
    if not base.is_dir():
        return {"ok": False, "error": f"sessions dir missing: {base}"}

    session_key_map: dict[str, tuple[str, str]] = {}
    sj = sessions_json or base / "sessions.json"
    if sj.exists():
        try:
            entries = json.loads(sj.read_text(encoding="utf-8"))
            for key, meta in entries.items():
                if not isinstance(meta, dict):
                    continue
                sid = meta.get("sessionId")
                if not sid:
                    continue
                if key.endswith(":main") and ":heartbeat" not in key:
                    session_key_map[sid] = ("browser", "main")
                elif key.endswith(":main:heartbeat"):
                    session_key_map[sid] = ("browser", "main:heartbeat")
        except json.JSONDecodeError:
            pass

    results = []
    for path in sorted(base.glob("*.jsonl")):
        if ".checkpoint." in path.name or path.name.startswith("."):
            continue
        stem = path.stem.split("-topic-")[0]
        channel, chat_id = session_key_map.get(stem, ("openclaw", stem[:48]))
        sk = f"agent:{agent_id}:{chat_id}" if channel == "browser" else None
        results.append(
            store.sync_openclaw_transcript(
                path,
                channel=channel,
                external_chat_id=chat_id,
                session_key=sk,
            )
        )
    return {"ok": True, "sessions": results, "mapped_main": len(session_key_map)}
