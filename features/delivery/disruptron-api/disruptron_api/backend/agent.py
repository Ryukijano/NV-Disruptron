from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass

from disruptron_api.context import get_context_store

logger = logging.getLogger(__name__)

AGENT_UNAVAILABLE = (
    "NV Disruptron backend is temporarily unavailable. "
    "Ensure NemoClaw / OpenClaw is running."
)


@dataclass(frozen=True, slots=True)
class AgentTurn:
    channel: str
    chat_id: str
    text: str


class AgentChatEngine:
    def __init__(self, *, agent_id: str, timeout_s: float) -> None:
        self._agent_id = agent_id
        self._timeout_s = timeout_s

    async def ask(self, turn: AgentTurn) -> str:
        if not shutil.which("openclaw"):
            logger.warning("openclaw CLI not found")
            return AGENT_UNAVAILABLE

        store = get_context_store()
        session_id = store.openclaw_session_id_for(turn.channel, turn.chat_id)
        cmd = [
            "openclaw",
            "agent",
            "--agent",
            self._agent_id,
            "--session-id",
            session_id,
            "--message",
            turn.text,
            "--json",
            "--timeout",
            str(int(self._timeout_s)),
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
                return AGENT_UNAVAILABLE
            data = json.loads(stdout.decode())
            payloads = data.get("payloads") or []
            texts = [p.get("text", "") for p in payloads if p.get("text")]
            if texts:
                return "\n\n".join(t.strip() for t in texts if t.strip())
            summary = data.get("summary")
            if isinstance(summary, str) and summary.strip():
                return summary.strip()
            return AGENT_UNAVAILABLE
        except Exception as exc:
            logger.warning("openclaw agent error: %s", exc)
            return AGENT_UNAVAILABLE
