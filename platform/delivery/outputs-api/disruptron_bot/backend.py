from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from disruptron_bot.config import Settings
from disruptron_bot.context_persist import get_context_store, record_assistant_message, record_user_message

logger = logging.getLogger(__name__)

BACKEND_UNAVAILABLE = (
    "NV-Disruptron is temporarily unavailable. "
    "Ensure the OpenClaw / OpenClaw backend is running and "
    "DISRUPTRON_BACKEND_URL points at its chat endpoint."
)


@dataclass(slots=True)
class ChatRequest:
    chat_id: int
    user_id: int
    username: str | None
    text: str


class BackendClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._url = f"{settings.backend_url}{settings.backend_chat_path}"

    async def ask(self, request: ChatRequest) -> str:
        record_user_message("telegram", request.chat_id, request.text)
        store = get_context_store()
        session_id = store.openclaw_session_id_for("telegram", request.chat_id)
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
                if response.status_code == 404:
                    return await self._openclaw_fallback(request)
                response.raise_for_status()
                data = response.json()
                reply = data.get("reply") or data.get("message") or data.get("text")
                if isinstance(reply, str) and reply.strip():
                    record_assistant_message("telegram", request.chat_id, reply.strip())
                    return reply.strip()
                empty = "Received an empty reply from the backend."
                record_assistant_message("telegram", request.chat_id, empty)
                return empty
        except httpx.HTTPStatusError as exc:
            logger.warning("Backend HTTP %s: %s", exc.response.status_code, exc.response.text[:200])
            record_assistant_message("telegram", request.chat_id, BACKEND_UNAVAILABLE)
            return BACKEND_UNAVAILABLE
        except httpx.RequestError as exc:
            logger.warning("Backend unreachable at %s: %s", self._url, exc)
            reply = await self._openclaw_fallback(request, session_id=session_id)
            record_assistant_message("telegram", request.chat_id, reply)
            return reply

    async def _openclaw_fallback(self, request: ChatRequest, *, session_id: str) -> str:
        import asyncio
        import json
        import shutil

        if not shutil.which("openclaw"):
            return BACKEND_UNAVAILABLE

        cmd = [
            "openclaw",
            "agent",
            "--local",
            "--agent",
            "disruptron",
            "--session-id",
            session_id,
            "--message",
            request.text,
            "--json",
            "--timeout",
            str(int(self._settings.backend_timeout_s)),
            "--reply-channel",
            "telegram",
            "--reply-to",
            str(request.chat_id),
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.warning("openclaw agent failed: %s", stderr.decode()[:300])
                return BACKEND_UNAVAILABLE
            data = json.loads(stdout.decode())
            payloads = data.get("payloads") or []
            texts = [p.get("text", "") for p in payloads if p.get("text")]
            if texts:
                return "\n\n".join(t.strip() for t in texts if t.strip())
            return data.get("summary") or BACKEND_UNAVAILABLE
        except Exception as exc:
            logger.warning("openclaw fallback error: %s", exc)
            return BACKEND_UNAVAILABLE
