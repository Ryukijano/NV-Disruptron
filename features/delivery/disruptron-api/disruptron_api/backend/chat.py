from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field, model_validator

from disruptron_api.backend.agent import AGENT_UNAVAILABLE, AgentChatEngine, AgentTurn
from disruptron_api.context import record_assistant_message, record_user_message

logger = logging.getLogger(__name__)

BACKEND_UNAVAILABLE = AGENT_UNAVAILABLE


class WebChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    session_id: str | None = Field(None, max_length=128)
    user_id: str = Field("web-user", max_length=128)
    channel: str | None = Field(None, max_length=32)
    chat_id: str | None = Field(None, max_length=128)
    username: str | None = Field(None, max_length=128)

    @model_validator(mode="after")
    def _require_identity(self) -> WebChatRequest:
        has_channel = bool(self.channel and self.chat_id)
        has_session = bool(self.session_id)
        if not has_channel and not has_session:
            self.session_id = "web-default"
        return self


class WebChatResponse(BaseModel):
    reply: str


@dataclass(frozen=True, slots=True)
class NormalizedChat:
    channel: str
    chat_id: str
    user_id: str
    text: str


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
    ) -> None:
        self._url = f"{backend_url.rstrip('/')}{chat_path}"
        self._timeout = httpx.Timeout(timeout_s)
        self._chat_mode = chat_mode.strip().lower()
        self._agent = AgentChatEngine(agent_id=agent_id, timeout_s=timeout_s)

    async def ask(self, request: WebChatRequest) -> WebChatResponse:
        turn = _normalize(request)
        record_user_message(turn.channel, turn.chat_id, turn.text)

        reply: str | None = None
        if self._chat_mode in {"auto", "http"}:
            reply = await self._ask_http(turn)

        if reply is None and self._chat_mode in {"auto", "agent"}:
            reply = await self._agent.ask(
                AgentTurn(channel=turn.channel, chat_id=turn.chat_id, text=turn.text)
            )

        if reply is None:
            reply = BACKEND_UNAVAILABLE

        record_assistant_message(turn.channel, turn.chat_id, reply)
        return WebChatResponse(reply=reply)

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
