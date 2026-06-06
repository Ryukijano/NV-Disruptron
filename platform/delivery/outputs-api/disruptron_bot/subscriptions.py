from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

SubscriptionKind = Literal["alerts", "daily"]


@dataclass(slots=True)
class Subscriber:
    user_id: int
    chat_id: int
    username: str | None
    alerts: bool = False
    daily: bool = False
    updated_at: str = ""

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC).isoformat()


class SubscriptionStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._subscribers: dict[int, Subscriber] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        for entry in raw.get("subscribers", []):
            sub = Subscriber(**entry)
            self._subscribers[sub.user_id] = sub

    def _save(self) -> None:
        payload = {
            "subscribers": [asdict(s) for s in self._subscribers.values()],
            "updated_at": datetime.now(UTC).isoformat(),
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def upsert(self, user_id: int, chat_id: int, username: str | None) -> Subscriber:
        with self._lock:
            sub = self._subscribers.get(user_id)
            if sub is None:
                sub = Subscriber(user_id=user_id, chat_id=chat_id, username=username)
                self._subscribers[user_id] = sub
            else:
                sub.chat_id = chat_id
                sub.username = username
            sub.touch()
            self._save()
            return sub

    def set_flag(
        self,
        user_id: int,
        chat_id: int,
        username: str | None,
        kind: SubscriptionKind,
        enabled: bool,
    ) -> Subscriber:
        with self._lock:
            sub = self._subscribers.get(user_id)
            if sub is None:
                sub = Subscriber(user_id=user_id, chat_id=chat_id, username=username)
                self._subscribers[user_id] = sub
            else:
                sub.chat_id = chat_id
                sub.username = username
            if kind == "alerts":
                sub.alerts = enabled
            else:
                sub.daily = enabled
            sub.touch()
            self._save()
            return sub

    def is_subscribed(self, user_id: int, kind: SubscriptionKind) -> bool:
        sub = self._subscribers.get(user_id)
        if sub is None:
            return False
        return sub.alerts if kind == "alerts" else sub.daily

    def chat_ids_for(self, kind: SubscriptionKind) -> list[int]:
        with self._lock:
            if kind == "alerts":
                return [s.chat_id for s in self._subscribers.values() if s.alerts]
            return [s.chat_id for s in self._subscribers.values() if s.daily]

    def summary(self) -> dict[str, int]:
        with self._lock:
            return {
                "total": len(self._subscribers),
                "alerts": sum(1 for s in self._subscribers.values() if s.alerts),
                "daily": sum(1 for s in self._subscribers.values() if s.daily),
            }
