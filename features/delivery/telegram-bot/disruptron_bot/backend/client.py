from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from disruptron_bot.config import BotSettings

logger = logging.getLogger(__name__)

BACKEND_UNAVAILABLE = (
    "NV Disruptron is temporarily unavailable. "
    "Ensure disruptron-api is running on DISRUPTRON_BACKEND_URL."
)


@dataclass(slots=True)
class ChatRequest:
    chat_id: int
    user_id: int
    username: str | None
    text: str


class BackendClient:
    def __init__(self, settings: BotSettings) -> None:
        self._settings = settings
        self._url = f"{settings.backend_url}{settings.backend_chat_path}"

    async def ask(self, request: ChatRequest) -> str:
        payload = {
            "channel": "telegram",
            "chat_id": str(request.chat_id),
            "user_id": str(request.user_id),
            "username": request.username,
            "text": request.text,
        }
        timeout = httpx.Timeout(self._settings.backend_timeout_s)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self._url, json=payload)
                response.raise_for_status()
                data = response.json()
                reply = data.get("reply") or data.get("message") or data.get("text")
                if isinstance(reply, str) and reply.strip():
                    return reply.strip()
                return "Received an empty reply from the backend."
        except httpx.HTTPStatusError as exc:
            logger.warning("Backend HTTP %s: %s", exc.response.status_code, exc.response.text[:200])
            return BACKEND_UNAVAILABLE
        except httpx.RequestError as exc:
            logger.warning("Backend unreachable at %s: %s", self._url, exc)
            return BACKEND_UNAVAILABLE
