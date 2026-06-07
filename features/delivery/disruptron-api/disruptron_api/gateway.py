from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Protocol

from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from disruptron_api.backend.chat import ChatProxy, WebChatRequest, WebChatResponse
from disruptron_api.backend.transcribe import STT_UNAVAILABLE, TranscribeEngine
from disruptron_api.config import ApiSettings
from disruptron_api.events import (
    AgentEvent,
    EventBus,
    chat_done_sse,
    chat_error_sse,
    chat_status_sse,
)
from disruptron_api.integrations import integrations_snapshot
from disruptron_api.context import list_web_messages
from disruptron_api.alert_monitor import AlertMonitor
from disruptron_api.subscriptions import SubscriptionStore
from disruptron_api.web_session_store import WebSessionStore
from disruptron_api.personalization import PersonalizationStore, UserPreferences
from disruptron_api.tts import ELEVENLABS_UNAVAILABLE, ElevenLabsTTS

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


class WebSubscriptionRequest(BaseModel):
    session_id: str = Field(..., min_length=4, max_length=128)
    alerts: bool | None = None
    daily: bool | None = None


class WebSubscriptionResponse(BaseModel):
    session_id: str
    alerts: bool
    daily: bool


class WebSessionBootstrapRequest(BaseModel):
    session_id: str | None = Field(None, max_length=128)
    user_id: str = Field("web-user", max_length=128)


class WebMessageItem(BaseModel):
    id: str
    role: str
    text: str
    created_at: str | None = None


class WebSummaryItem(BaseModel):
    date: str
    title: str
    body: str
    updated_at: int


class WebNotificationItem(BaseModel):
    id: str
    title: str
    body: str
    kind: str = "alert"
    timestamp: int


class WebSessionBootstrapResponse(BaseModel):
    session_id: str
    messages: list[WebMessageItem]
    summaries: list[WebSummaryItem]
    notifications: list[WebNotificationItem]
    subscriptions: WebSubscriptionResponse


class WebSummaryUpsertRequest(BaseModel):
    session_id: str = Field(..., min_length=4, max_length=128)
    date: str = Field(..., min_length=10, max_length=10)
    title: str = Field(..., min_length=1, max_length=256)
    body: str = Field(..., min_length=1, max_length=16000)


class WebNotificationCreateRequest(BaseModel):
    session_id: str = Field(..., min_length=4, max_length=128)
    title: str = Field(..., min_length=1, max_length=256)
    body: str = Field("", max_length=4096)
    kind: str = Field("alert", max_length=32)
    id: str | None = Field(None, max_length=64)


class WebPreferencesRequest(BaseModel):
    session_id: str = Field(..., min_length=4, max_length=128)
    tube_lines: list[str] = Field(default_factory=list)
    areas: list[str] = Field(default_factory=list)
    ev_enabled: bool = False
    commute_morning: str = Field("07:00-09:30", max_length=32)
    commute_evening: str = Field("17:00-19:30", max_length=32)
    onboarding_complete: bool = False


class WebPreferencesResponse(BaseModel):
    session_id: str
    tube_lines: list[str]
    areas: list[str]
    ev_enabled: bool
    commute_morning: str
    commute_evening: str
    onboarding_complete: bool


class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=480)


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
    *,
    web_store: WebSubscriptionStore | None = None,
    web_session: WebSessionStore | None = None,
    events: EventBus | None = None,
    scheduler: DigestScheduler | None = None,
    alert_monitor: AlertMonitor | None = None,
    personalization: PersonalizationStore | None = None,
    tts: ElevenLabsTTS | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if scheduler is not None and settings.scheduler_enabled:
            scheduler.start()
        if alert_monitor is not None:
            alert_monitor.start()
        yield
        if alert_monitor is not None:
            await alert_monitor.stop()
        if scheduler is not None:
            await scheduler.stop()

    app = FastAPI(
        title="NV Disruptron Outputs API",
        description="Frontend-agnostic gateway for web, Telegram, and push delivery.",
        version="0.3.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    async def _broadcast_web(
        text: str,
        *,
        title: str,
        kind: str,
        web_kind: str,
    ) -> None:
        if web_store is None:
            return
        session_ids = web_store.session_ids_for(web_kind)  # type: ignore[arg-type]
        if not session_ids:
            return
        today = datetime.now(UTC).date().isoformat()
        for sid in session_ids:
            if web_session is not None:
                web_session.add_notification(
                    sid, title=title, body=text, kind=kind
                )
                if kind == "daily":
                    web_session.upsert_summary(
                        sid, date=today, title=title, body=text
                    )
            if events is not None:
                event = AgentEvent.now(title=title, body=text, kind=kind)
                await events.publish(event, session_ids=[sid])

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "disruptron-outputs-api"}

    @app.get("/v1/integrations")
    async def integrations_status() -> dict[str, object]:
        snapshot = await integrations_snapshot()
        return {
            **snapshot,
            "scheduler": {
                "enabled": settings.scheduler_enabled,
                "daily_digest": f"{settings.daily_digest_hour:02d}:{settings.daily_digest_minute:02d} Europe/London",
            },
            "agent": {
                "local": settings.agent_local,
                "chat_mode": settings.chat_mode,
                "interactive_agent_id": settings.agent_id,
                "autonomous_agent_id": settings.autonomous_agent_id,
                "timeout_s": settings.backend_timeout_s,
            },
        }

    @app.get("/v1/subscriptions")
    async def subscriptions(
        authorization: str | None = Header(None),
        x_push_secret: str | None = Header(None, alias="X-Push-Secret"),
    ) -> dict[str, int]:
        _check_secret(settings, authorization, x_push_secret)
        summary = store.summary()
        if web_store is not None:
            web_summary = web_store.summary()
            summary["web_total"] = web_summary["total"]
            summary["web_alerts"] = web_summary["alerts"]
            summary["web_daily"] = web_summary["daily"]
        return summary

    @app.post("/v1/web/session", response_model=WebSessionBootstrapResponse)
    async def bootstrap_web_session(body: WebSessionBootstrapRequest) -> WebSessionBootstrapResponse:
        if web_session is None or web_store is None:
            raise HTTPException(status_code=503, detail="Web session store not configured")
        sid = web_session.ensure_session(body.session_id, user_id=body.user_id)
        sub = web_store.get(sid)
        raw_messages = list_web_messages(sid)
        summaries = web_session.list_summaries(sid)
        notifications = web_session.list_notifications(sid)
        return WebSessionBootstrapResponse(
            session_id=sid,
            messages=[WebMessageItem(**m) for m in raw_messages],
            summaries=[
                WebSummaryItem(
                    date=s.date,
                    title=s.title,
                    body=s.body,
                    updated_at=s.updated_at,
                )
                for s in summaries
            ],
            notifications=[
                WebNotificationItem(
                    id=n.id,
                    title=n.title,
                    body=n.body,
                    kind=n.kind,
                    timestamp=n.timestamp,
                )
                for n in notifications
            ],
            subscriptions=WebSubscriptionResponse(
                session_id=sub.session_id,
                alerts=sub.alerts,
                daily=sub.daily,
            ),
        )

    @app.get("/v1/web/messages", response_model=list[WebMessageItem])
    async def get_web_messages(
        session_id: str = Query(..., min_length=4),
        limit: int = Query(100, ge=1, le=200),
    ) -> list[WebMessageItem]:
        return [WebMessageItem(**m) for m in list_web_messages(session_id, limit=limit)]

    @app.get("/v1/web/summaries", response_model=list[WebSummaryItem])
    async def get_web_summaries(
        session_id: str = Query(..., min_length=4),
        limit: int = Query(60, ge=1, le=120),
    ) -> list[WebSummaryItem]:
        if web_session is None:
            raise HTTPException(status_code=503, detail="Web session store not configured")
        return [
            WebSummaryItem(date=s.date, title=s.title, body=s.body, updated_at=s.updated_at)
            for s in web_session.list_summaries(session_id, limit=limit)
        ]

    @app.put("/v1/web/summaries", response_model=WebSummaryItem)
    async def put_web_summary(body: WebSummaryUpsertRequest) -> WebSummaryItem:
        if web_session is None:
            raise HTTPException(status_code=503, detail="Web session store not configured")
        row = web_session.upsert_summary(
            body.session_id,
            date=body.date,
            title=body.title,
            body=body.body,
        )
        return WebSummaryItem(
            date=row.date, title=row.title, body=row.body, updated_at=row.updated_at
        )

    @app.get("/v1/web/notifications", response_model=list[WebNotificationItem])
    async def get_web_notifications(
        session_id: str = Query(..., min_length=4),
        limit: int = Query(100, ge=1, le=200),
    ) -> list[WebNotificationItem]:
        if web_session is None:
            raise HTTPException(status_code=503, detail="Web session store not configured")
        return [
            WebNotificationItem(
                id=n.id, title=n.title, body=n.body, kind=n.kind, timestamp=n.timestamp
            )
            for n in web_session.list_notifications(session_id, limit=limit)
        ]

    @app.post("/v1/web/notifications", response_model=WebNotificationItem)
    async def post_web_notification(body: WebNotificationCreateRequest) -> WebNotificationItem:
        if web_session is None:
            raise HTTPException(status_code=503, detail="Web session store not configured")
        row = web_session.add_notification(
            body.session_id,
            title=body.title,
            body=body.body,
            kind=body.kind,
            notification_id=body.id,
        )
        return WebNotificationItem(
            id=row.id, title=row.title, body=row.body, kind=row.kind, timestamp=row.timestamp
        )

    @app.get("/v1/web/preferences", response_model=WebPreferencesResponse)
    async def get_web_preferences(session_id: str = Query(..., min_length=4)) -> WebPreferencesResponse:
        if personalization is None:
            raise HTTPException(status_code=503, detail="Personalization store not configured")
        prefs = personalization.get(session_id)
        return WebPreferencesResponse(session_id=session_id, **prefs.to_dict())

    @app.put("/v1/web/preferences", response_model=WebPreferencesResponse)
    async def put_web_preferences(body: WebPreferencesRequest) -> WebPreferencesResponse:
        if personalization is None:
            raise HTTPException(status_code=503, detail="Personalization store not configured")
        prefs = UserPreferences(
            tube_lines=body.tube_lines,
            areas=body.areas,
            ev_enabled=body.ev_enabled,
            commute_morning=body.commute_morning,
            commute_evening=body.commute_evening,
            onboarding_complete=body.onboarding_complete,
        )
        saved = personalization.save(body.session_id, prefs)
        return WebPreferencesResponse(session_id=body.session_id, **saved.to_dict())

    @app.get("/v1/web/subscriptions", response_model=WebSubscriptionResponse)
    async def get_web_subscriptions(session_id: str = Query(..., min_length=4)) -> WebSubscriptionResponse:
        if web_store is None:
            raise HTTPException(status_code=503, detail="Web subscriptions not configured")
        sub = web_store.get(session_id)
        return WebSubscriptionResponse(session_id=sub.session_id, alerts=sub.alerts, daily=sub.daily)

    @app.put("/v1/web/subscriptions", response_model=WebSubscriptionResponse)
    async def put_web_subscriptions(body: WebSubscriptionRequest) -> WebSubscriptionResponse:
        if web_store is None:
            raise HTTPException(status_code=503, detail="Web subscriptions not configured")
        sub = web_store.set_flags(
            body.session_id,
            alerts=body.alerts,
            daily=body.daily,
        )
        return WebSubscriptionResponse(session_id=sub.session_id, alerts=sub.alerts, daily=sub.daily)

    @app.get("/v1/events/stream")
    async def events_stream(session_id: str = Query(..., min_length=4)) -> StreamingResponse:
        if events is None:
            raise HTTPException(status_code=503, detail="Event stream not configured")

        async def generate() -> AsyncIterator[str]:
            async for chunk in events.heartbeat_sse(session_id):
                yield chunk

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

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
        result = PushResponse(status="ok", delivered=0, failed=0, targets=[])
        if chat_ids:
            result = await _deliver(body.message, chat_ids)
        await _broadcast_web(
            body.message,
            title="Transport alert",
            kind="alert",
            web_kind="alerts",
        )
        return result

    @app.post("/v1/push/daily", response_model=PushResponse)
    async def push_daily(
        body: PushRequest,
        authorization: str | None = Header(None),
        x_push_secret: str | None = Header(None, alias="X-Push-Secret"),
    ) -> PushResponse:
        _check_secret(settings, authorization, x_push_secret)
        chat_ids = [body.chat_id] if body.chat_id is not None else store.chat_ids_for("daily")
        result = PushResponse(status="ok", delivered=0, failed=0, targets=[])
        if chat_ids:
            result = await _deliver(body.message, chat_ids)
        await _broadcast_web(
            body.message,
            title="Morning briefing",
            kind="daily",
            web_kind="daily",
        )
        return result

    @app.post("/v1/digest/run")
    async def run_digest_now(
        authorization: str | None = Header(None),
        x_push_secret: str | None = Header(None, alias="X-Push-Secret"),
    ) -> dict[str, str]:
        _check_secret(settings, authorization, x_push_secret)
        if scheduler is None:
            raise HTTPException(status_code=503, detail="Scheduler not configured")
        reply = await scheduler.run_now()
        return {"status": "ok", "reply": reply[:500]}

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

    @app.post("/v1/chat/stream")
    async def web_chat_stream(body: WebChatRequest) -> StreamingResponse:
        if chat is None:
            raise HTTPException(status_code=503, detail="Chat proxy not configured")

        async def generate() -> AsyncIterator[str]:
            yield chat_status_sse("Routing your request…")

            async def on_event(chunk: str) -> None:
                nonlocal queue
                await queue.put(chunk)

            queue: asyncio.Queue[str | None] = asyncio.Queue()

            async def run_chat() -> None:
                try:
                    response = await chat.ask(body, on_stream=on_event)
                    await queue.put(chat_done_sse(response.reply))
                except Exception as exc:
                    logger.warning("chat stream failed: %s", exc)
                    await queue.put(chat_error_sse("Could not reach disruptron-api. Try again."))
                finally:
                    await queue.put(None)

            task = asyncio.create_task(run_chat())
            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    yield item
            finally:
                await task

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/v1/chat/image")
    async def web_chat_image(
        text: str = Query(..., min_length=1, max_length=8000),
        session_id: str = Query(..., min_length=4),
        image: UploadFile = File(...),
    ) -> WebChatResponse:
        if chat is None:
            raise HTTPException(status_code=503, detail="Chat proxy not configured")
        import tempfile
        from pathlib import Path

        suffix = Path(image.filename or "upload.jpg").suffix or ".jpg"
        payload = await image.read()
        if not payload:
            raise HTTPException(status_code=400, detail="Empty image")
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(payload)
            image_path = tmp.name
        body = WebChatRequest(text=text, session_id=session_id, image_path=image_path)
        return await chat.ask(body)

    @app.post("/v1/tts")
    async def synthesize_tts(body: TtsRequest) -> StreamingResponse:
        if tts is None or not tts.configured:
            raise HTTPException(status_code=503, detail=ELEVENLABS_UNAVAILABLE)
        try:
            audio = await tts.synthesize(body.text)
        except Exception as exc:
            logger.warning("TTS failed: %s", exc)
            raise HTTPException(status_code=502, detail="TTS synthesis failed") from exc
        return StreamingResponse(
            iter([audio]),
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-store"},
        )

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
