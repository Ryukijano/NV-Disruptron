from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from disruptron_bot.context_api import create_context_router
from telegram.error import TelegramError

if TYPE_CHECKING:
    from telegram import Bot

    from disruptron_bot.config import Settings
    from disruptron_bot.subscriptions import SubscriptionStore

logger = logging.getLogger(__name__)


class PushRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096)
    chat_id: int | None = Field(
        None,
        description="Optional target chat. Omit to fan out to all subscribers.",
    )


class PushResponse(BaseModel):
    status: str
    delivered: int
    failed: int
    targets: list[int]


def _check_secret(settings: Settings, authorization: str | None, x_push_secret: str | None) -> None:
    secret = settings.push_secret
    if not secret:
        return
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif x_push_secret:
        token = x_push_secret.strip()
    if token != secret:
        raise HTTPException(status_code=401, detail="Invalid push secret")


def create_app(settings: Settings, store: SubscriptionStore, bot: Bot) -> FastAPI:
    app = FastAPI(
        title="NV-Disruptron Outputs API",
        description="Push gateway for Telegram alerts and daily plans. "
        "Interactive chat is handled by the co-located Telegram bot.",
        version="0.2.0",
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "disruptron-outputs-api"}

    @app.get("/v1/subscriptions")
    async def subscriptions(
        authorization: str | None = Header(None),
        x_push_secret: str | None = Header(None, alias="X-Push-Secret"),
    ) -> dict[str, int]:
        _check_secret(settings, authorization, x_push_secret)
        return store.summary()

    async def _deliver(text: str, chat_ids: list[int]) -> PushResponse:
        delivered = 0
        failed = 0
        for chat_id in chat_ids:
            try:
                await bot.send_message(chat_id=chat_id, text=text)
                delivered += 1
            except TelegramError as exc:
                failed += 1
                logger.warning("push to %s failed: %s", chat_id, exc)
        return PushResponse(
            status="ok",
            delivered=delivered,
            failed=failed,
            targets=chat_ids,
        )

    @app.post("/v1/push/alert", response_model=PushResponse)
    async def push_alert(
        body: PushRequest,
        authorization: str | None = Header(None),
        x_push_secret: str | None = Header(None, alias="X-Push-Secret"),
    ) -> PushResponse:
        _check_secret(settings, authorization, x_push_secret)
        chat_ids = [body.chat_id] if body.chat_id is not None else store.chat_ids_for("alerts")
        if not chat_ids:
            return PushResponse(status="ok", delivered=0, failed=0, targets=[])
        return await _deliver(body.message, chat_ids)

    @app.post("/v1/push/daily", response_model=PushResponse)
    async def push_daily(
        body: PushRequest,
        authorization: str | None = Header(None),
        x_push_secret: str | None = Header(None, alias="X-Push-Secret"),
    ) -> PushResponse:
        _check_secret(settings, authorization, x_push_secret)
        chat_ids = [body.chat_id] if body.chat_id is not None else store.chat_ids_for("daily")
        if not chat_ids:
            return PushResponse(status="ok", delivered=0, failed=0, targets=[])
        return await _deliver(body.message, chat_ids)

    def _auth(authorization: str | None, x_push_secret: str | None) -> None:
        _check_secret(settings, authorization, x_push_secret)

    app.include_router(create_context_router(_auth))

    @app.post("/v1/outputs", response_model=PushResponse)
    async def legacy_outputs(
        body: PushRequest,
        authorization: str | None = Header(None),
        x_push_secret: str | None = Header(None, alias="X-Push-Secret"),
    ) -> PushResponse:
        return await push_alert(body, authorization, x_push_secret)

    return app
