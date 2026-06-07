from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from disruptron_api.config import REPO_ROOT

logger = logging.getLogger(__name__)

_SHARED = REPO_ROOT / "platform" / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from context_store import ContextStore, conversation_id  # noqa: E402

_DEFAULT_DB = REPO_ROOT / "data" / "disruptron_context.db"
_store: ContextStore | None = None


def get_context_store() -> ContextStore:
    global _store
    if _store is None:
        db = os.environ.get("DISRUPTRON_CONTEXT_DB", str(_DEFAULT_DB))
        _store = ContextStore(db)
    return _store


def record_user_message(channel: str, chat_id: str | int, text: str) -> None:
    try:
        get_context_store().append_message(
            channel=channel,
            external_chat_id=chat_id,
            role="user",
            content=text,
        )
    except Exception:
        logger.exception("context store: failed to record user message")


def record_assistant_message(channel: str, chat_id: str | int, text: str) -> None:
    try:
        get_context_store().append_message(
            channel=channel,
            external_chat_id=chat_id,
            role="assistant",
            content=text,
        )
    except Exception:
        logger.exception("context store: failed to record assistant message")


def list_web_messages(session_id: str, *, limit: int = 100) -> list[dict[str, object]]:
    cid = conversation_id("web", session_id)
    store = get_context_store()
    messages = store.list_messages(cid, limit=limit)
    return [
        {
            "id": str(msg.id),
            "role": msg.role,
            "text": msg.content,
            "created_at": msg.created_at,
        }
        for msg in messages
        if msg.role in {"user", "assistant"} and msg.content.strip()
    ]
