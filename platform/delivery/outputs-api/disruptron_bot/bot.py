from __future__ import annotations

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from disruptron_bot.backend import BackendClient
from disruptron_bot.config import Settings
from disruptron_bot.handlers import build_handlers
from disruptron_bot.subscriptions import SubscriptionStore


def build_application(
    settings: Settings,
    store: SubscriptionStore,
    backend: BackendClient,
) -> Application:
    handlers = build_handlers(settings, store, backend)
    app = (
        Application.builder()
        .token(settings.bot_token)
        .concurrent_updates(True)
        .build()
    )

    app.add_handler(CommandHandler("start", handlers["start"]))
    app.add_handler(CommandHandler("help", handlers["help"]))
    app.add_handler(CommandHandler("subscribe_alerts", handlers["subscribe_alerts"]))
    app.add_handler(CommandHandler("unsubscribe_alerts", handlers["unsubscribe_alerts"]))
    app.add_handler(CommandHandler("subscribe_daily", handlers["subscribe_daily"]))
    app.add_handler(CommandHandler("unsubscribe_daily", handlers["unsubscribe_daily"]))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handlers["direct_chat"])
    )

    app.bot_data["settings"] = settings
    app.bot_data["store"] = store
    app.bot_data["backend"] = backend
    return app
