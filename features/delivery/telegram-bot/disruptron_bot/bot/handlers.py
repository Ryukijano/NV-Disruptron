from __future__ import annotations

import logging

from disruptron_api.subscriptions import SubscriptionStore
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes

from disruptron_bot.backend import BackendClient, ChatRequest
from disruptron_bot.bot import messages as msg
from disruptron_bot.config import BotSettings

logger = logging.getLogger(__name__)


def _authorized(settings: BotSettings, user_id: int | None) -> bool:
    if user_id is None:
        return False
    if settings.allow_from is None:
        return True
    return user_id in settings.allow_from


async def _deny(update: Update) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(msg.DENIED)


def build_handlers(
    settings: BotSettings,
    store: SubscriptionStore,
    backend: BackendClient,
) -> dict[str, object]:
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(settings, update.effective_user and update.effective_user.id):
            await _deny(update)
            return
        await update.effective_message.reply_text(msg.WELCOME, parse_mode=ParseMode.HTML)

    async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(settings, update.effective_user and update.effective_user.id):
            await _deny(update)
            return
        await update.effective_message.reply_text(msg.HELP, parse_mode=ParseMode.HTML)

    async def subscribe_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        chat = update.effective_chat
        if not user or not chat or not _authorized(settings, user.id):
            await _deny(update)
            return
        store.set_flag(user.id, chat.id, user.username, "alerts", True)
        await update.effective_message.reply_text(msg.SUBSCRIBED_ALERTS, parse_mode=ParseMode.HTML)

    async def unsubscribe_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        chat = update.effective_chat
        if not user or not chat or not _authorized(settings, user.id):
            await _deny(update)
            return
        store.set_flag(user.id, chat.id, user.username, "alerts", False)
        await update.effective_message.reply_text(msg.UNSUBSCRIBED_ALERTS)

    async def subscribe_daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        chat = update.effective_chat
        if not user or not chat or not _authorized(settings, user.id):
            await _deny(update)
            return
        store.set_flag(user.id, chat.id, user.username, "daily", True)
        await update.effective_message.reply_text(msg.SUBSCRIBED_DAILY, parse_mode=ParseMode.HTML)

    async def unsubscribe_daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        chat = update.effective_chat
        if not user or not chat or not _authorized(settings, user.id):
            await _deny(update)
            return
        store.set_flag(user.id, chat.id, user.username, "daily", False)
        await update.effective_message.reply_text(msg.UNSUBSCRIBED_DAILY)

    async def direct_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        user = update.effective_user
        chat = update.effective_chat
        if not message or not message.text or not user or not chat:
            return
        if not _authorized(settings, user.id):
            await _deny(update)
            return

        store.upsert(user.id, chat.id, user.username)
        await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)
        status = await message.reply_text(msg.THINKING)

        request = ChatRequest(
            chat_id=chat.id,
            user_id=user.id,
            username=user.username,
            text=message.text,
        )
        try:
            reply = await backend.ask(request)
        except Exception:
            logger.exception("chat handler failed for user %s", user.id)
            await status.edit_text("Something went wrong forwarding your message. Please try again.")
            return

        if len(reply) > 4000:
            reply = reply[:3990] + "…"
        await status.edit_text(reply)

    return {
        "start": start,
        "help": help_cmd,
        "subscribe_alerts": subscribe_alerts,
        "unsubscribe_alerts": unsubscribe_alerts,
        "subscribe_daily": subscribe_daily,
        "unsubscribe_daily": unsubscribe_daily,
        "direct_chat": direct_chat,
    }
