from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

WebSubscriptionKind = Literal["alerts", "daily"]


@dataclass(slots=True)
class WebSubscriber:
    session_id: str
    alerts: bool = False
    daily: bool = False
    updated_at: str = ""

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC).isoformat()


class WebSubscriptionStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._subscribers: dict[str, WebSubscriber] = {}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        for entry in raw.get("subscribers", []):
            sub = WebSubscriber(**entry)
            self._subscribers[sub.session_id] = sub

    def _save(self) -> None:
        payload = {
            "subscribers": [asdict(s) for s in self._subscribers.values()],
            "updated_at": datetime.now(UTC).isoformat(),
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def get(self, session_id: str) -> WebSubscriber:
        with self._lock:
            sub = self._subscribers.get(session_id)
            if sub is None:
                sub = WebSubscriber(session_id=session_id)
                self._subscribers[session_id] = sub
            return WebSubscriber(**asdict(sub))

    def set_flags(
        self,
        session_id: str,
        *,
        alerts: bool | None = None,
        daily: bool | None = None,
    ) -> WebSubscriber:
        with self._lock:
            sub = self._subscribers.get(session_id)
            if sub is None:
                sub = WebSubscriber(session_id=session_id)
                self._subscribers[session_id] = sub
            if alerts is not None:
                sub.alerts = alerts
            if daily is not None:
                sub.daily = daily
            sub.touch()
            self._save()
            return WebSubscriber(**asdict(sub))

    def session_ids_for(self, kind: WebSubscriptionKind) -> list[str]:
        with self._lock:
            if kind == "alerts":
                return [s.session_id for s in self._subscribers.values() if s.alerts]
            return [s.session_id for s in self._subscribers.values() if s.daily]

    def summary(self) -> dict[str, int]:
        with self._lock:
            return {
                "total": len(self._subscribers),
                "alerts": sum(1 for s in self._subscribers.values() if s.alerts),
                "daily": sum(1 for s in self._subscribers.values() if s.daily),
            }
