from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

BACKEND_UNAVAILABLE = (
    "NV Disruptron backend is temporarily unavailable. "
    "Ensure NemoClaw / OpenClaw is running."
)


class WebChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    session_id: str = Field("web-default", max_length=128)
    user_id: str = Field("web-user", max_length=128)


class WebChatResponse(BaseModel):
    reply: str


class ChatProxy:
    def __init__(self, backend_url: str, chat_path: str, timeout_s: float) -> None:
        self._url = f"{backend_url.rstrip('/')}{chat_path}"
        self._timeout = httpx.Timeout(timeout_s)

    async def ask(self, request: WebChatRequest) -> WebChatResponse:
        payload = {
            "channel": "web",
            "chat_id": request.session_id,
            "user_id": request.user_id,
            "text": request.text,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self._url, json=payload)
                if response.status_code == 404:
                    return WebChatResponse(reply=BACKEND_UNAVAILABLE)
                response.raise_for_status()
                data = response.json()
                reply = data.get("reply") or data.get("message") or data.get("text")
                if isinstance(reply, str) and reply.strip():
                    return WebChatResponse(reply=reply.strip())
                return WebChatResponse(reply="Received an empty reply from the backend.")
        except httpx.HTTPStatusError as exc:
            logger.warning("chat proxy HTTP %s", exc.response.status_code)
            return WebChatResponse(reply=BACKEND_UNAVAILABLE)
        except httpx.RequestError as exc:
            logger.warning("chat proxy unreachable at %s: %s", self._url, exc)
            return WebChatResponse(reply=BACKEND_UNAVAILABLE)
