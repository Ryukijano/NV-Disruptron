"""REST routes for NV-Disruptron conversation context (SQLite)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

# platform/shared on path when running from outputs-api venv
_SHARED = Path(__file__).resolve().parents[3] / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from context_store import ContextStore, conversation_id, sync_all_openclaw_sessions  # noqa: E402


class ConversationUpsert(BaseModel):
    channel: str = Field(..., min_length=1, max_length=64)
    chat_id: str = Field(..., min_length=1, max_length=128)
    session_key: str | None = None
    openclaw_session_id: str | None = None
    title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MessageAppend(BaseModel):
    channel: str
    chat_id: str
    role: str
    content: str
    run_id: str | None = None
    content_type: str = "text"
    media: dict[str, Any] = Field(default_factory=dict)
    input_tokens: int | None = None
    output_tokens: int | None = None
    session_key: str | None = None
    openclaw_session_id: str | None = None


class FactAppend(BaseModel):
    fact_text: str = Field(..., min_length=1)
    scope: str = "global"
    conversation_id: str | None = None
    fact_key: str | None = None
    source_run_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class CompactionAppend(BaseModel):
    channel: str
    chat_id: str
    summary: str
    run_id: str | None = None
    tokens_before: int | None = None


def _db_path() -> Path:
    root = os.environ.get("DISRUPTRON_ROOT", Path(__file__).resolve().parents[4])
    return Path(os.environ.get("DISRUPTRON_CONTEXT_DB", Path(root) / "data" / "disruptron_context.db"))


def _store() -> ContextStore:
    return ContextStore(_db_path())


def create_context_router(check_secret) -> APIRouter:
    router = APIRouter(prefix="/v1/context", tags=["context"])

    @router.get("/health")
    async def context_health() -> dict[str, str]:
        store = _store()
        return {"status": "ok", "db": str(store.db_path)}

    @router.get("/conversations")
    async def list_conversations(
        channel: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        authorization: str | None = Header(None),
        x_push_secret: str | None = Header(None, alias="X-Push-Secret"),
    ) -> list[dict[str, Any]]:
        check_secret(authorization, x_push_secret)
        store = _store()
        return [
            {
                "id": c.id,
                "channel": c.channel,
                "chat_id": c.external_chat_id,
                "session_key": c.session_key,
                "openclaw_session_id": c.openclaw_session_id,
                "title": c.title,
                "updated_at": c.updated_at,
            }
            for c in store.list_conversations(channel=channel, limit=limit)
        ]

    @router.post("/conversations")
    async def upsert_conversation(
        body: ConversationUpsert,
        authorization: str | None = Header(None),
        x_push_secret: str | None = Header(None, alias="X-Push-Secret"),
    ) -> dict[str, Any]:
        check_secret(authorization, x_push_secret)
        c = _store().upsert_conversation(
            channel=body.channel,
            external_chat_id=body.chat_id,
            session_key=body.session_key,
            openclaw_session_id=body.openclaw_session_id,
            title=body.title,
            metadata=body.metadata,
        )
        return {"id": c.id, "openclaw_session_id": c.openclaw_session_id}

    @router.get("/conversations/{cid}/messages")
    async def list_messages(
        cid: str,
        limit: int = Query(50, ge=1, le=500),
        authorization: str | None = Header(None),
        x_push_secret: str | None = Header(None, alias="X-Push-Secret"),
    ) -> list[dict[str, Any]]:
        check_secret(authorization, x_push_secret)
        msgs = _store().list_messages(cid, limit=limit)
        return [
            {
                "id": m.id,
                "run_id": m.run_id,
                "role": m.role,
                "content": m.content,
                "content_type": m.content_type,
                "media": m.media,
                "input_tokens": m.input_tokens,
                "output_tokens": m.output_tokens,
                "created_at": m.created_at,
            }
            for m in msgs
        ]

    @router.post("/messages")
    async def append_message(
        body: MessageAppend,
        authorization: str | None = Header(None),
        x_push_secret: str | None = Header(None, alias="X-Push-Secret"),
    ) -> dict[str, Any]:
        check_secret(authorization, x_push_secret)
        m = _store().append_message(
            channel=body.channel,
            external_chat_id=body.chat_id,
            role=body.role,
            content=body.content,
            run_id=body.run_id,
            content_type=body.content_type,
            media=body.media,
            input_tokens=body.input_tokens,
            output_tokens=body.output_tokens,
            session_key=body.session_key,
            openclaw_session_id=body.openclaw_session_id,
        )
        return {"id": m.id, "conversation_id": m.conversation_id, "run_id": m.run_id}

    @router.get("/recall")
    async def recall(
        channel: str,
        chat_id: str,
        max_chars: int = Query(2800, ge=500, le=12000),
        authorization: str | None = Header(None),
        x_push_secret: str | None = Header(None, alias="X-Push-Secret"),
    ) -> dict[str, Any]:
        check_secret(authorization, x_push_secret)
        return _store().recall(channel=channel, external_chat_id=chat_id, max_chars=max_chars)

    @router.post("/facts")
    async def add_fact(
        body: FactAppend,
        authorization: str | None = Header(None),
        x_push_secret: str | None = Header(None, alias="X-Push-Secret"),
    ) -> dict[str, int]:
        check_secret(authorization, x_push_secret)
        fid = _store().add_fact(
            fact_text=body.fact_text,
            scope=body.scope,
            conversation_id=body.conversation_id,
            fact_key=body.fact_key,
            source_run_id=body.source_run_id,
            tags=body.tags,
        )
        return {"id": fid}

    @router.get("/facts/search")
    async def search_facts(
        q: str = "",
        scope: str | None = None,
        conversation_id: str | None = None,
        limit: int = Query(10, ge=1, le=50),
        authorization: str | None = Header(None),
        x_push_secret: str | None = Header(None, alias="X-Push-Secret"),
    ) -> list[dict[str, Any]]:
        check_secret(authorization, x_push_secret)
        return _store().search_facts(q, scope=scope, conversation_id=conversation_id, limit=limit)

    @router.post("/sync/openclaw")
    async def sync_openclaw(
        authorization: str | None = Header(None),
        x_push_secret: str | None = Header(None, alias="X-Push-Secret"),
    ) -> dict[str, Any]:
        check_secret(authorization, x_push_secret)
        return sync_all_openclaw_sessions(_store())

    @router.get("/session-id")
    async def resolve_session_id(
        channel: str,
        chat_id: str,
        authorization: str | None = Header(None),
        x_push_secret: str | None = Header(None, alias="X-Push-Secret"),
    ) -> dict[str, str]:
        check_secret(authorization, x_push_secret)
        sid = _store().openclaw_session_id_for(channel, chat_id)
        return {
            "conversation_id": conversation_id(channel, chat_id),
            "openclaw_session_id": sid,
        }

    return router
