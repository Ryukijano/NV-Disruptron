from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class AgentEvent:
    id: str
    title: str
    body: str
    timestamp: int
    kind: str = "alert"
    session_id: str | None = None

    def to_sse(self) -> str:
        payload = {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "timestamp": self.timestamp,
            "kind": self.kind,
        }
        return f"data: {json.dumps(payload)}\n\n"

    @classmethod
    def now(cls, *, title: str, body: str = "", kind: str = "alert") -> AgentEvent:
        return cls(
            id=f"evt-{datetime.now(UTC).timestamp()}",
            title=title,
            body=body,
            timestamp=int(datetime.now(UTC).timestamp() * 1000),
            kind=kind,
        )


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, asyncio.Queue[str]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, session_id: str) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=64)
        async with self._lock:
            self._subscribers[session_id] = queue
        return queue

    async def unsubscribe(self, session_id: str) -> None:
        async with self._lock:
            self._subscribers.pop(session_id, None)

    async def publish(
        self,
        event: AgentEvent,
        *,
        session_ids: list[str] | None = None,
    ) -> None:
        message = event.to_sse()
        async with self._lock:
            targets = (
                {sid: self._subscribers[sid] for sid in session_ids if sid in self._subscribers}
                if session_ids
                else dict(self._subscribers)
            )
        for queue in targets.values():
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                pass

    async def heartbeat_sse(self, session_id: str) -> AsyncIterator[str]:
        queue = await self.subscribe(session_id)
        try:
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=25.0)
                    yield message
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            await self.unsubscribe(session_id)


def chat_status_sse(text: str) -> str:
    return f"data: {json.dumps({'type': 'status', 'text': text})}\n\n"


def chat_done_sse(reply: str) -> str:
    return f"data: {json.dumps({'type': 'done', 'reply': reply})}\n\n"


def chat_error_sse(message: str) -> str:
    return f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"


def chat_mode_sse(mode: str, agent_id: str, reason: str) -> str:
    return f"data: {json.dumps({'type': 'mode', 'mode': mode, 'agent_id': agent_id, 'reason': reason})}\n\n"


def chat_tool_sse(tool: str, status: str, detail: str = "") -> str:
    return f"data: {json.dumps({'type': 'tool', 'tool': tool, 'status': status, 'detail': detail})}\n\n"


def chat_ui_sse(blocks: list[dict], title: str, variant: str = "info") -> str:
    return f"data: {json.dumps({'type': 'ui', 'title': title, 'variant': variant, 'blocks': blocks})}\n\n"


def chat_panel_sse(kind: str, title: str, ttl_ms: int = 15000) -> str:
    """Emit a tactical panel directive — triggers a COD-tablet card on the frontend."""
    return f"data: {json.dumps({'type': 'panel', 'kind': kind, 'title': title, 'ttlMs': ttl_ms})}\n\n"


def chat_route_sse(
    kind: str, title: str, coordinates: list[list[float]], ttl_ms: int = 30000
) -> str:
    """Emit a route coordinate payload so the frontend can draw the actual TfL journey on the map."""
    return f"data: {json.dumps({'type': 'route', 'kind': kind, 'title': title, 'coordinates': coordinates, 'ttlMs': ttl_ms})}\n\n"
