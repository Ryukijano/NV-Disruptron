from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from disruptron_api.backend.agent import AgentChatEngine, AgentTurn
from disruptron_api.events import AgentEvent, EventBus
from disruptron_api.subscriptions import SubscriptionStore
from disruptron_api.web_session_store import WebSessionStore
from disruptron_api.web_subscriptions import WebSubscriptionStore

logger = logging.getLogger(__name__)

LONDON = ZoneInfo("Europe/London")

MORNING_PROMPT = (
    "Generate today's morning briefing for London mobility. "
    "Call disruptron_ops__get_london_city_briefing first. "
    "If google-calendar MCP is available, include the next 4 hours of calendar events "
    "(titles only in text, never read private details aloud). "
    "Include tube lines, road congestion, and EV charging near user areas from USER.md. "
    "Start the reply with the phrase 'Morning briefing'."
)


class DigestScheduler:
    """Runs the morning digest at a fixed London time. Heartbeat alerts stay on OpenClaw."""

    def __init__(
        self,
        *,
        agent: AgentChatEngine,
        telegram_store: SubscriptionStore,
        web_store: WebSubscriptionStore,
        events: EventBus,
        delivery,
        digest_hour: int,
        digest_minute: int,
        state_path: Path,
        web_session: WebSessionStore | None = None,
    ) -> None:
        self._agent = agent
        self._telegram_store = telegram_store
        self._web_store = web_store
        self._events = events
        self._delivery = delivery
        self._web_session = web_session
        self._digest_hour = digest_hour
        self._digest_minute = digest_minute
        self._state_path = state_path
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="disruptron-digest")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def run_now(self) -> str:
        """Manual trigger (e.g. demo / test). Returns agent reply."""
        return await self._run_daily_digest()

    def _load_state(self) -> dict[str, str]:
        if not self._state_path.exists():
            return {}
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _save_state(self, state: dict[str, str]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    async def _run(self) -> None:
        logger.info(
            "Morning digest scheduler started (daily %02d:%02d Europe/London)",
            self._digest_hour,
            self._digest_minute,
        )
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("digest scheduler tick failed: %s", exc)
            await asyncio.sleep(60.0)

    async def _tick(self) -> None:
        now = datetime.now(LONDON)
        state = self._load_state()
        today = now.date().isoformat()
        if (
            now.hour == self._digest_hour
            and now.minute == self._digest_minute
            and state.get("last_daily") != today
        ):
            await self._run_daily_digest()
            state["last_daily"] = today
            self._save_state(state)

    async def _run_daily_digest(self) -> str:
        logger.info("Running morning digest")
        reply = await self._agent.ask(
            AgentTurn(channel="system", chat_id="daily-digest", text=MORNING_PROMPT)
        )
        if not reply or reply.strip().upper() == "HEARTBEAT_OK":
            logger.info("Morning digest empty — skipping push")
            return reply or ""

        telegram_ids = self._telegram_store.chat_ids_for("daily")
        for chat_id in telegram_ids:
            try:
                await self._delivery.send(chat_id, reply)
            except Exception as exc:
                logger.warning("daily push to %s failed: %s", chat_id, exc)

        web_ids = self._web_store.session_ids_for("daily")
        today = datetime.now(LONDON).date().isoformat()
        for sid in web_ids:
            if self._web_session is not None:
                self._web_session.add_notification(
                    sid, title="Morning briefing", body=reply, kind="daily"
                )
                self._web_session.upsert_summary(
                    sid, date=today, title="Morning briefing", body=reply
                )
        event = AgentEvent.now(title="Morning briefing", body=reply, kind="daily")
        await self._events.publish(event, session_ids=web_ids or None)
        return reply
