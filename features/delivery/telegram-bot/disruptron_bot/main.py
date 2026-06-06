from __future__ import annotations

import asyncio
import logging
import signal

from disruptron_api.subscriptions import SubscriptionStore
from telegram import BotCommand
from telegram.ext import Application

from disruptron_bot.backend import BackendClient
from disruptron_bot.bot import build_application
from disruptron_bot.config import BotSettings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    BotCommand("start", "Welcome and menu"),
    BotCommand("help", "How to use NV Disruptron"),
    BotCommand("subscribe_alerts", "Push disruption alerts"),
    BotCommand("unsubscribe_alerts", "Stop disruption alerts"),
    BotCommand("subscribe_daily", "Morning daily plan digest"),
    BotCommand("unsubscribe_daily", "Stop daily plan digest"),
]


async def main_async() -> None:
    settings = BotSettings.from_env()
    store = SubscriptionStore(settings.subscriptions_path)
    backend = BackendClient(settings)
    application = build_application(settings, store, backend)

    logger.info("NV Disruptron Telegram bot starting")
    logger.info("Backend chat plug-in: %s%s", settings.backend_url, settings.backend_chat_path)

    await application.initialize()
    await application.bot.set_my_commands(BOT_COMMANDS)
    await application.start()
    await application.updater.start_polling(
        allowed_updates=["message"],
        drop_pending_updates=True,
    )

    stop = asyncio.Event()

    def _signal_handler() -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass

    await stop.wait()

    await application.updater.stop()
    await application.stop()
    await application.shutdown()


def run() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    run()
