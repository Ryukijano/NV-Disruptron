from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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
