from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from disruptron_bot.config import Settings
from disruptron_bot.gateway import create_app
from disruptron_bot.subscriptions import SubscriptionStore


class _FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


@pytest.fixture
def store(tmp_path: Path) -> SubscriptionStore:
    path = tmp_path / "subscriptions.json"
    return SubscriptionStore(path)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        bot_token="test-token",
        push_host="127.0.0.1",
        push_port=8010,
        push_secret="secret",
        backend_url="http://127.0.0.1:18789",
        backend_chat_path="/v1/chat",
        backend_timeout_s=30.0,
        subscriptions_path=tmp_path / "subscriptions.json",
        allow_from=None,
    )


def test_subscription_store_roundtrip(store: SubscriptionStore) -> None:
    store.set_flag(42, 4200, "alice", "alerts", True)
    store.set_flag(42, 4200, "alice", "daily", True)
    store.set_flag(99, 9900, "bob", "alerts", True)

    assert store.is_subscribed(42, "alerts")
    assert store.is_subscribed(42, "daily")
    assert store.chat_ids_for("alerts") == [4200, 9900]
    assert store.chat_ids_for("daily") == [4200]

    store.set_flag(42, 4200, "alice", "alerts", False)
    assert not store.is_subscribed(42, "alerts")
    assert store.chat_ids_for("alerts") == [9900]


def test_push_alert_fanout(settings: Settings, store: SubscriptionStore) -> None:
    store.set_flag(1, 100, "u1", "alerts", True)
    store.set_flag(2, 200, "u2", "daily", True)

    bot = _FakeBot()
    app = create_app(settings, store, bot)  # type: ignore[arg-type]
    client = TestClient(app)

    response = client.post(
        "/v1/push/alert",
        json={"message": "Jubilee delayed"},
        headers={"X-Push-Secret": "secret"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["delivered"] == 1
    assert body["targets"] == [100]


def test_push_requires_secret(settings: Settings, store: SubscriptionStore) -> None:
    bot = _FakeBot()
    app = create_app(settings, store, bot)  # type: ignore[arg-type]
    client = TestClient(app)

    response = client.post("/v1/push/daily", json={"message": "Plan"})
    assert response.status_code == 401


def test_health(settings: Settings, store: SubscriptionStore) -> None:
    bot = _FakeBot()
    app = create_app(settings, store, bot)  # type: ignore[arg-type]
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"


def test_subscription_persistence(tmp_path: Path) -> None:
    path = tmp_path / "subscriptions.json"
    first = SubscriptionStore(path)
    first.set_flag(7, 700, "tester", "daily", True)

    second = SubscriptionStore(path)
    assert second.is_subscribed(7, "daily")
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["subscribers"][0]["chat_id"] == 700
