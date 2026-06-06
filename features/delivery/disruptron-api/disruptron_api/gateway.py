from __future__ import annotations

import logging
from typing import Protocol

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from disruptron_api.backend.chat import ChatProxy, WebChatRequest, WebChatResponse
from disruptron_api.backend.transcribe import STT_UNAVAILABLE, TranscribeEngine
from disruptron_api.config import ApiSettings
from disruptron_api.subscriptions import SubscriptionStore

logger = logging.getLogger(__name__)


class MessageDelivery(Protocol):
    async def send(self, chat_id: int, text: str) -> None: ...


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


class TranscribeResponse(BaseModel):
    text: str


def _check_secret(settings: ApiSettings, authorization: str | None, x_push_secret: str | None) -> None:
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


def create_app(
    settings: ApiSettings,
    store: SubscriptionStore,
    delivery: MessageDelivery,
    chat: ChatProxy | None = None,
    transcribe: TranscribeEngine | None = None,
) -> FastAPI:
    app = FastAPI(
        title="NV Disruptron Outputs API",
        description="Frontend-agnostic gateway for web, Telegram, and push delivery.",
        version="0.2.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
                await delivery.send(chat_id, text)
                delivered += 1
            except Exception as exc:
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

    @app.post("/v1/outputs", response_model=PushResponse)
    async def legacy_outputs(
        body: PushRequest,
        authorization: str | None = Header(None),
        x_push_secret: str | None = Header(None, alias="X-Push-Secret"),
    ) -> PushResponse:
        return await push_alert(body, authorization, x_push_secret)

    @app.post("/v1/chat", response_model=WebChatResponse)
    async def web_chat(body: WebChatRequest) -> WebChatResponse:
        if chat is None:
            raise HTTPException(status_code=503, detail="Chat proxy not configured")
        return await chat.ask(body)

    @app.post("/v1/transcribe", response_model=TranscribeResponse)
    async def transcribe_audio(
        audio: UploadFile = File(...),
    ) -> TranscribeResponse:
        if transcribe is None:
            raise HTTPException(status_code=503, detail="Speech transcription not configured")
        payload = await audio.read()
        if not payload:
            raise HTTPException(status_code=400, detail="Empty audio payload")
        text = await transcribe.transcribe(
            payload,
            audio.filename or "audio.webm",
            audio.content_type or "application/octet-stream",
        )
        if text == STT_UNAVAILABLE:
            raise HTTPException(status_code=503, detail=STT_UNAVAILABLE)
        return TranscribeResponse(text=text)

    return app
