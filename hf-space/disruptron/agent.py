from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AgentTurn:
    channel: str
    chat_id: str
    text: str
    image_path: str | None = None


@dataclass(frozen=True, slots=True)
class AgentResult:
    reply: str
    tool_kinds: list[str]


class AgentChatEngine:
    def __init__(self, *, model_url: str, model_name: str) -> None:
        self._model_url = model_url.rstrip("/")
        self._model_name = model_name

    def _system_prompt(self) -> str:
        return (
            "You are NV-Disruptron, a helpful AI assistant for London mobility and transport. "
            "You answer concisely about TfL disruptions, road congestion, and accessibility. "
            "Use available tools when needed. If you lack live data, say so and suggest what to check."
        )

    async def ask(self, turn: AgentTurn) -> AgentResult:
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": turn.text},
        ]
        payload: dict[str, Any] = {
            "model": self._model_name,
            "messages": messages,
            "max_tokens": 512,
            "temperature": 0.7,
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self._model_url}/chat/completions",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content", "") or ""
            return AgentResult(reply=content.strip(), tool_kinds=[])
        except Exception as exc:
            logger.warning("vLLM chat failed: %s", exc)
            return AgentResult(
                reply="NV-Disruptron is warming up. Please try again in a few seconds.",
                tool_kinds=[],
            )
