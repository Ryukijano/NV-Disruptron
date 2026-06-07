from __future__ import annotations

import logging
from pathlib import Path

import uvicorn

from disruptron_api.alert_monitor import AlertMonitor
from disruptron_api.backend.agent import AgentChatEngine
from disruptron_api.backend.chat import ChatProxy
from disruptron_api.config import ApiSettings
from disruptron_api.delivery.telegram import TelegramDelivery
from disruptron_api.events import EventBus
from disruptron_api.gateway import create_app
from disruptron_api.personalization import PersonalizationStore
from disruptron_api.scheduler import DigestScheduler
from disruptron_api.stt_factory import build_transcribe_engine
from disruptron_api.subscriptions import SubscriptionStore
from disruptron_api.tts import ElevenLabsTTS
from disruptron_api.web_session_store import WebSessionStore
from disruptron_api.web_subscriptions import WebSubscriptionStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run() -> None:
    settings = ApiSettings.from_env()
    store = SubscriptionStore(settings.subscriptions_path)
    web_store = WebSubscriptionStore(settings.web_subscriptions_path)
    web_session = WebSessionStore(settings.web_session_db_path)
    events = EventBus()
    delivery = TelegramDelivery(settings.telegram_bot_token)
    agent = AgentChatEngine(
        agent_id=settings.agent_id,
        timeout_s=settings.backend_timeout_s,
        local=settings.agent_local,
    )
    chat = ChatProxy(
        settings.backend_url,
        settings.backend_chat_path,
        settings.backend_timeout_s,
        chat_mode=settings.chat_mode,
        agent_id=settings.agent_id,
        autonomous_agent_id=settings.autonomous_agent_id,
        agent_local=settings.agent_local,
        own_port=settings.push_port_for_guard,
    )
    scheduler = DigestScheduler(
        agent=agent,
        telegram_store=store,
        web_store=web_store,
        events=events,
        delivery=delivery,
        digest_hour=settings.daily_digest_hour,
        digest_minute=settings.daily_digest_minute,
        state_path=settings.scheduler_state_path,
        web_session=web_session,
    )
    alert_monitor = AlertMonitor(
        web_store=web_store,
        web_session=web_session,
        events=events,
        state_path=settings.scheduler_state_path.parent / "alert_monitor_state.json",
    )
    repo_root = Path(__file__).resolve().parents[4]
    personalization = PersonalizationStore(
        settings.web_session_db_path,
        user_md_path=repo_root / "features" / "agent" / "workspace" / "USER.md",
    )
    tts = ElevenLabsTTS.from_env()
    transcribe = build_transcribe_engine(settings)
    app = create_app(
        settings,
        store,
        delivery,
        chat,
        transcribe,
        web_store=web_store,
        web_session=web_session,
        events=events,
        scheduler=scheduler,
        alert_monitor=alert_monitor,
        personalization=personalization,
        tts=tts,
    )

    logger.info(
        "NV Disruptron outputs API listening on %s:%s (agent_local=%s, routes=%s/%s)",
        settings.push_host,
        settings.push_port,
        settings.agent_local,
        settings.agent_id,
        settings.autonomous_agent_id,
    )
    uvicorn.run(app, host=settings.push_host, port=settings.push_port, log_level="info")


if __name__ == "__main__":
    run()
