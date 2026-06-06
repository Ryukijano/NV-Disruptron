from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from disruptron_api.backend.chat import ChatProxy, WebChatRequest
from disruptron_api.config import ApiSettings
from disruptron_api.gateway import create_app
from disruptron_api.subscriptions import SubscriptionStore


class _FakeDelivery:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


class _FakeTranscribe:
    async def transcribe(self, audio: bytes, filename: str, content_type: str) -> str:
        del filename, content_type
        if not audio:
            return "Speech transcription is temporarily unavailable."
        return "central line delayed"


@pytest.fixture
def store(tmp_path: Path) -> SubscriptionStore:
    return SubscriptionStore(tmp_path / "subscriptions.json")


@pytest.fixture
def settings(tmp_path: Path) -> ApiSettings:
    return ApiSettings(
        push_host="127.0.0.1",
        push_port=8010,
        push_secret="secret",
        telegram_bot_token="test-token",
        subscriptions_path=tmp_path / "subscriptions.json",
        backend_url="http://127.0.0.1:18789",
        backend_chat_path="/v1/chat",
        backend_timeout_s=30.0,
        chat_mode="auto",
        agent_id="disruptron",
        stt_engine="off",
        stt_url="http://127.0.0.1:8000/v1/audio/transcriptions",
        stt_model="whisper-1",
        stt_device="cpu",
        stt_compute_type="int8",
        stt_timeout_s=30.0,
        cors_origins=("http://localhost:5173",),
    )


def test_subscription_store_roundtrip(store: SubscriptionStore) -> None:
    store.set_flag(42, 4200, "alice", "alerts", True)
    store.set_flag(42, 4200, "alice", "daily", True)
    store.set_flag(99, 9900, "bob", "alerts", True)

    assert store.is_subscribed(42, "alerts")
    assert store.chat_ids_for("alerts") == [4200, 9900]

    store.set_flag(42, 4200, "alice", "alerts", False)
    assert store.chat_ids_for("alerts") == [9900]


def test_push_alert_fanout(settings: ApiSettings, store: SubscriptionStore) -> None:
    store.set_flag(1, 100, "u1", "alerts", True)
    store.set_flag(2, 200, "u2", "daily", True)

    delivery = _FakeDelivery()
    client = TestClient(create_app(settings, store, delivery))

    response = client.post(
        "/v1/push/alert",
        json={"message": "Jubilee delayed"},
        headers={"X-Push-Secret": "secret"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["delivered"] == 1
    assert delivery.sent == [(100, "Jubilee delayed")]


def test_push_requires_secret(settings: ApiSettings, store: SubscriptionStore) -> None:
    delivery = _FakeDelivery()
    client = TestClient(create_app(settings, store, delivery))
    assert client.post("/v1/push/daily", json={"message": "Plan"}).status_code == 401


def test_transcribe_endpoint(settings: ApiSettings, store: SubscriptionStore) -> None:
    delivery = _FakeDelivery()
    client = TestClient(create_app(settings, store, delivery, transcribe=_FakeTranscribe()))
    response = client.post(
        "/v1/transcribe",
        files={"audio": ("clip.webm", b"fake-audio", "audio/webm")},
    )
    assert response.status_code == 200
    assert response.json()["text"] == "central line delayed"


def test_subscription_persistence(tmp_path: Path) -> None:
    path = tmp_path / "subscriptions.json"
    SubscriptionStore(path).set_flag(7, 700, "tester", "daily", True)
    assert SubscriptionStore(path).is_subscribed(7, "daily")
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["subscribers"][0]["chat_id"] == 700


@pytest.mark.asyncio
async def test_chat_auto_falls_back_to_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISRUPTRON_CONTEXT_DB", str(tmp_path / "context.db"))
    proxy = ChatProxy(
        "http://127.0.0.1:18789",
        "/v1/chat",
        30.0,
        chat_mode="auto",
        agent_id="disruptron",
    )

    with patch.object(proxy, "_ask_http", AsyncMock(return_value=None)):
        with patch.object(proxy._agent, "ask", AsyncMock(return_value="Agent reply")):
            response = await proxy.ask(
                WebChatRequest(text="Hello", session_id="web-test", user_id="web-user")
            )

    assert response.reply == "Agent reply"


@pytest.mark.asyncio
async def test_chat_telegram_payload_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISRUPTRON_CONTEXT_DB", str(tmp_path / "context.db"))
    proxy = ChatProxy(
        "http://127.0.0.1:8010",
        "/v1/chat",
        30.0,
        chat_mode="agent",
        agent_id="disruptron",
    )

    with patch.object(proxy._agent, "ask", AsyncMock(return_value="Tube status OK")) as agent_ask:
        response = await proxy.ask(
            WebChatRequest(
                text="Status?",
                channel="telegram",
                chat_id="4200",
                user_id="42",
                username="alice",
            )
        )

    assert response.reply == "Tube status OK"
    agent_ask.assert_awaited_once()
    turn = agent_ask.await_args.args[0]
    assert turn.channel == "telegram"
    assert turn.chat_id == "4200"


@pytest.mark.asyncio
async def test_chat_http_mode_skips_agent() -> None:
    proxy = ChatProxy(
        "http://127.0.0.1:18789",
        "/v1/chat",
        30.0,
        chat_mode="http",
        agent_id="disruptron",
    )

    with patch.object(proxy, "_ask_http", AsyncMock(return_value="HTTP reply")):
        with patch.object(proxy._agent, "ask", AsyncMock()) as agent_ask:
            response = await proxy.ask(WebChatRequest(text="Hi", session_id="web-1"))

    assert response.reply == "HTTP reply"
    agent_ask.assert_not_awaited()
