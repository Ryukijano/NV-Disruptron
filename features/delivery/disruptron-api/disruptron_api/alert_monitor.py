"""Real threshold-based alerts from live MCP briefing (no simulation)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from disruptron_api.briefing_client import fetch_london_briefing, material_change
from disruptron_api.events import AgentEvent, EventBus
from disruptron_api.web_session_store import WebSessionStore
from disruptron_api.web_subscriptions import WebSubscriptionStore

logger = logging.getLogger(__name__)

CHECK_INTERVAL_S = 600.0  # 10 minutes — aligns with HEARTBEAT


class AlertMonitor:
    def __init__(
        self,
        *,
        web_store: WebSubscriptionStore,
        web_session: WebSessionStore | None,
        events: EventBus,
        state_path: Path,
    ) -> None:
        self._web_store = web_store
        self._web_session = web_session
        self._events = events
        self._state_path = state_path
        self._task: asyncio.Task[None] | None = None
        self._last_briefing: dict | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="disruptron-alert-monitor")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def _load_state(self) -> dict:
        if not self._state_path.exists():
            return {}
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _save_state(self, state: dict) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    async def _run(self) -> None:
        logger.info("Alert monitor started (interval %.0fs)", CHECK_INTERVAL_S)
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("alert monitor tick failed: %s", exc)
            await asyncio.sleep(CHECK_INTERVAL_S)

    async def _tick(self) -> None:
        briefing = await fetch_london_briefing()
        prev = self._last_briefing
        changed, title = material_change(prev, briefing)
        self._last_briefing = briefing

        if not changed or not title:
            return

        body = (briefing.get("summary") or "")[:2000]
        session_ids = self._web_store.session_ids_for("alerts")
        if not session_ids:
            return

        for sid in session_ids:
            if self._web_session is not None:
                self._web_session.add_notification(sid, title=title, body=body, kind="alert")
            event = AgentEvent.now(title=title, body=body, kind="alert")
            await self._events.publish(event, session_ids=[sid])

        state = self._load_state()
        state["last_alert_at"] = datetime.now(UTC).isoformat()
        state["last_alert_title"] = title
        self._save_state(state)
        logger.info("Material change alert: %s", title)
