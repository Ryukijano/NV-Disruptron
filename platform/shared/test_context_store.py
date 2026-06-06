"""Tests for platform/shared/context_store.py"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SHARED = Path(__file__).resolve().parent
sys.path.insert(0, str(SHARED))

from context_store import ContextStore, conversation_id  # noqa: E402


@pytest.fixture
def store(tmp_path: Path) -> ContextStore:
    return ContextStore(tmp_path / "test.db")


def test_conversation_and_messages(store: ContextStore) -> None:
    store.append_message(
        channel="browser",
        external_chat_id="main",
        role="user",
        content="Hello",
        run_id="run-1",
    )
    store.append_message(
        channel="browser",
        external_chat_id="main",
        role="assistant",
        content="Hi there",
        run_id="run-1",
    )
    cid = conversation_id("browser", "main")
    msgs = store.list_messages(cid)
    assert len(msgs) == 2
    assert msgs[0].content == "Hello"
    assert msgs[1].run_id == "run-1"


def test_recall_includes_facts_and_messages(store: ContextStore) -> None:
    store.add_fact(fact_text="Jubilee line delayed", fact_key="tube", scope="global")
    store.append_message(channel="browser", external_chat_id="main", role="user", content="status?")
    out = store.recall(channel="browser", external_chat_id="main")
    assert out["found"] is True
    assert "Jubilee" in out["recall_text"]
    assert "status?" in out["recall_text"]


def test_stable_openclaw_session_id(store: ContextStore) -> None:
    a = store.openclaw_session_id_for("telegram", 12345)
    b = store.openclaw_session_id_for("telegram", 12345)
    assert a == b
    assert a.startswith("disruptron-")


def test_sync_openclaw_jsonl(store: ContextStore, tmp_path: Path) -> None:
    jsonl = tmp_path / "sess-abc.jsonl"
    jsonl.write_text(
        "\n".join(
            [
                json.dumps({"type": "session", "id": "sess-abc"}),
                json.dumps(
                    {
                        "type": "message",
                        "id": "m1",
                        "message": {"role": "user", "content": "Brief me"},
                    }
                ),
                json.dumps(
                    {
                        "type": "message",
                        "id": "m2",
                        "message": {"role": "assistant", "content": "Three lines delayed"},
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    result = store.sync_openclaw_transcript(jsonl, channel="browser", external_chat_id="main")
    assert result["ok"] is True
    assert result["imported"] == 2
    recall = store.recall(channel="browser", external_chat_id="main")
    assert "Brief me" in recall["recall_text"]
