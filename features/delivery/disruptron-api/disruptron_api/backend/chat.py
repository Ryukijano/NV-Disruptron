from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field, model_validator

from disruptron_api.backend.agent import AGENT_UNAVAILABLE, AgentChatEngine, AgentTurn
from disruptron_api.backend.router import RouteDecision, classify_intent
from disruptron_api.briefing_client import briefing_to_ui_blocks, fetch_london_briefing
from disruptron_api.context import record_assistant_message, record_user_message

logger = logging.getLogger(__name__)

BACKEND_UNAVAILABLE = AGENT_UNAVAILABLE

StreamCallback = Callable[[str], Awaitable[None] | None]


class WebChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    session_id: str | None = Field(None, max_length=128)
    user_id: str = Field("web-user", max_length=128)
    channel: str | None = Field(None, max_length=32)
    chat_id: str | None = Field(None, max_length=128)
    username: str | None = Field(None, max_length=128)
    image_path: str | None = Field(None, max_length=512)

    @model_validator(mode="after")
    def _require_identity(self) -> WebChatRequest:
        has_channel = bool(self.channel and self.chat_id)
        has_session = bool(self.session_id)
        if not has_channel and not has_session:
            self.session_id = "web-default"
        return self


class WebChatResponse(BaseModel):
    reply: str
    route: str | None = None
    agent_id: str | None = None


@dataclass(frozen=True, slots=True)
class NormalizedChat:
    channel: str
    chat_id: str
    user_id: str
    text: str
    image_path: str | None


def _normalize(request: WebChatRequest) -> NormalizedChat:
    if request.channel and request.chat_id:
        channel = request.channel.strip().lower()
        chat_id = request.chat_id
    else:
        channel = "web"
        chat_id = request.session_id or "web-default"
    return NormalizedChat(
        channel=channel,
        chat_id=chat_id,
        user_id=request.user_id,
        text=request.text,
        image_path=request.image_path,
    )


def _extract_reply(data: object) -> str | None:
    if not isinstance(data, dict):
        return None
    reply = data.get("reply") or data.get("message") or data.get("text")
    if isinstance(reply, str) and reply.strip():
        return reply.strip()
    return None


class ChatProxy:
    def __init__(
        self,
        backend_url: str,
        chat_path: str,
        timeout_s: float,
        *,
        chat_mode: str = "auto",
        agent_id: str = "disruptron",
        autonomous_agent_id: str = "disruptron",
        agent_local: bool = True,
        own_port: int | None = None,
    ) -> None:
        self._backend_url = backend_url.rstrip("/")
        self._url = f"{self._backend_url}{chat_path}"
        self._timeout = httpx.Timeout(timeout_s)
        self._chat_mode = chat_mode.strip().lower()
        self._agent_id = agent_id
        self._autonomous_agent_id = autonomous_agent_id
        self._agent = AgentChatEngine(
            agent_id=agent_id, timeout_s=timeout_s, local=agent_local
        )
        self._own_port = own_port

    def _http_backend_is_self(self) -> bool:
        if self._own_port is None:
            return False
        return f":{self._own_port}" in self._backend_url

    async def _emit(self, callback: StreamCallback | None, payload: str) -> None:
        if callback is None:
            return
        result = callback(payload)
        if result is not None:
            await result

    async def _prefetch_briefing(self, callback: StreamCallback | None) -> dict | None:
        from disruptron_api.events import chat_tool_sse, chat_ui_sse

        await self._emit(callback, chat_tool_sse("disruptron_ops__get_london_city_briefing", "start"))
        try:
            briefing = await fetch_london_briefing()
            await self._emit(
                callback,
                chat_tool_sse(
                    "disruptron_ops__get_london_city_briefing",
                    "done",
                    (briefing.get("summary") or "")[:120],
                ),
            )
            blocks = briefing_to_ui_blocks(briefing)
            await self._emit(
                callback,
                chat_ui_sse(blocks, "Live London briefing", "info"),
            )
            return briefing
        except Exception as exc:
            logger.warning("briefing prefetch failed: %s", exc)
            await self._emit(
                callback,
                chat_tool_sse("disruptron_ops__get_london_city_briefing", "error", str(exc)[:120]),
            )
            return None

    async def ask(
        self,
        request: WebChatRequest,
        *,
        on_stream: StreamCallback | None = None,
    ) -> WebChatResponse:
        turn = _normalize(request)
        record_user_message(turn.channel, turn.chat_id, turn.text)

        from disruptron_api.events import chat_mode_sse

        decision = classify_intent(
            turn.text,
            interactive_agent_id=self._agent_id,
            autonomous_agent_id=self._autonomous_agent_id,
            has_image=bool(turn.image_path),
        )
        await self._emit(
            on_stream,
            chat_mode_sse(decision.route.value, decision.agent_id, decision.reason),
        )

        if decision.prefetch_briefing:
            await self._prefetch_briefing(on_stream)

        reply: str | None = None
        if self._chat_mode in {"auto", "http"} and not self._http_backend_is_self():
            reply = await self._ask_http(turn)

        if reply is None and self._chat_mode in {"auto", "agent"}:
            from disruptron_api.events import chat_tool_sse

            await self._emit(
                on_stream,
                chat_tool_sse(f"openclaw:{decision.agent_id}", "start", decision.reason),
            )
            reply = await self._agent.ask(
                AgentTurn(
                    channel=turn.channel,
                    chat_id=turn.chat_id,
                    text=turn.text,
                    image_path=turn.image_path,
                ),
                agent_id=decision.agent_id,
            )
            await self._emit(
                on_stream,
                chat_tool_sse(f"openclaw:{decision.agent_id}", "done"),
            )

        if reply is None:
            reply = BACKEND_UNAVAILABLE

        record_assistant_message(turn.channel, turn.chat_id, reply)
        return WebChatResponse(
            reply=reply,
            route=decision.route.value,
            agent_id=decision.agent_id,
        )

    async def _ask_http(self, turn: NormalizedChat) -> str | None:
        payload = {
            "channel": turn.channel,
            "chat_id": turn.chat_id,
            "user_id": turn.user_id,
            "text": turn.text,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self._url, json=payload)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                reply = _extract_reply(response.json())
                if reply:
                    return reply
                return "Received an empty reply from the backend."
        except httpx.HTTPStatusError as exc:
            logger.warning("chat proxy HTTP %s", exc.response.status_code)
            return None
        except httpx.RequestError as exc:
            logger.warning("chat proxy unreachable at %s: %s", self._url, exc)
            return None
