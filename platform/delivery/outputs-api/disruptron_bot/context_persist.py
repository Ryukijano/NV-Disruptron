"""Persist Telegram / backend chat turns in SQLite."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_REPO = Path(__file__).resolve().parents[4]
if str(_REPO / "platform" / "shared") not in sys.path:
    sys.path.insert(0, str(_REPO / "platform" / "shared"))

from context_store import ContextStore  # noqa: E402


def get_context_store() -> ContextStore:
    import os

    db = os.environ.get("DISRUPTRON_CONTEXT_DB", str(_REPO / "data" / "disruptron_context.db"))
    return ContextStore(db)


def record_user_message(channel: str, chat_id: str | int, text: str, *, run_id: str | None = None) -> None:
    try:
        get_context_store().append_message(
            channel=channel,
            external_chat_id=chat_id,
            role="user",
            content=text,
            run_id=run_id,
        )
    except Exception:
        logger.exception("context store: failed to record user message")


def record_assistant_message(
    channel: str,
    chat_id: str | int,
    text: str,
    *,
    run_id: str | None = None,
    output_tokens: int | None = None,
) -> None:
    try:
        get_context_store().append_message(
            channel=channel,
            external_chat_id=chat_id,
            role="assistant",
            content=text,
            run_id=run_id,
            output_tokens=output_tokens,
        )
    except Exception:
        logger.exception("context store: failed to record assistant message")
