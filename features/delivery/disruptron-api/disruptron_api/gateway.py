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

    # --- GeoJSON map layers ---
    @app.get("/v1/geo/hazards")
    async def get_hazard_geojson() -> dict:
        """Return hazard reports as GeoJSON FeatureCollection for map rendering."""
        from pathlib import Path
        import json

        geojson_path = Path(__file__).resolve().parents[4] / "data" / "geo" / "hazards.geojson"
        if geojson_path.exists():
            with geojson_path.open(encoding="utf-8") as f:
                return json.load(f)
        return {"type": "FeatureCollection", "features": []}

    @app.get("/v1/geo/wards")
    async def get_ward_geojson() -> dict:
        """Return London ward boundaries as GeoJSON (placeholder until GeoParquet pipeline is live)."""
        # TODO: Load from data/geo/wards.geojson once cuSpatial ETL pipeline generates it
        return {
            "type": "FeatureCollection",
            "features": [],
            "_meta": {
                "note": "Ward GeoJSON will be generated by the cuSpatial pipeline (Workstream 3).",
                "source": "London Datastore CKAN GIS boundaries",
            },
        }

    @app.post("/v1/hazard/upload")
    async def upload_hazard_image(
        image: UploadFile = File(...),
        lat: float | None = Query(None),
        lon: float | None = Query(None),
    ) -> dict:
        """Upload a street image for hazard detection and map it.

        Args:
            image: Photo of potential hazard.
            lat: Optional explicit latitude.
            lon: Optional explicit longitude.
        """
        import tempfile
        from pathlib import Path

        suffix = Path(image.filename or "upload.jpg").suffix or ".jpg"
        payload = await image.read()
        if not payload:
            raise HTTPException(status_code=400, detail="Empty image")
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(payload)
            image_path = tmp.name

        # Run hazard analysis
        from features.vision.hazard_pipeline import analyze_street_image, report_hazard

        records = await analyze_street_image(image_path, lat, lon)

        if records:
            result = await report_hazard(records)
            return {
                "status": "analyzed",
                "hazards_detected": len(records),
                **result,
            }
        return {"status": "no_hazards_detected", "hazards_detected": 0}

    # --- Video ingestion endpoints ---
    @app.post("/v1/video/upload")
    async def upload_video(
        video: UploadFile = File(...),
        lat: float | None = Query(None),
        lon: float | None = Query(None),
        target_fps: float = Query(0.5, ge=0.1, le=10.0),
        confidence_threshold: float = Query(0.3, ge=0.0, le=1.0),
        min_event_duration_sec: float = Query(1.0, ge=0.0, le=300.0),
    ) -> dict:
        """Upload a video for temporal hazard detection.

        Processes video through LocateAnything-3B with IoU-based temporal
        tracking to detect *persistent* accessibility hazards.

        Args:
            video: Video file (mp4, mov, avi).
            lat: Optional latitude for geotagging.
            lon: Optional longitude for geotagging.
            target_fps: Frame sampling rate (default 0.5 = 1 frame / 2 sec).
            confidence_threshold: Min detection confidence.
            min_event_duration_sec: Filter out events shorter than this.
        """
        import tempfile
        from pathlib import Path

        suffix = Path(video.filename or "upload.mp4").suffix or ".mp4"
        payload = await video.read()
        if not payload:
            raise HTTPException(status_code=400, detail="Empty video")
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(payload)
            video_path = tmp.name

        from features.vision.video_pipeline import analyze_video

        result = await analyze_video(
            video_path=video_path,
            lat=lat,
            lon=lon,
            target_fps=target_fps,
            confidence_threshold=confidence_threshold,
            min_event_duration_sec=min_event_duration_sec,
        )
        return result

    @app.get("/v1/video/events")
    def get_video_events(
        category: str | None = Query(None),
        borough: str | None = Query(None),
        min_duration_sec: float | None = Query(None),
        limit: int = Query(100, ge=1, le=1000),
    ) -> list[dict]:
        """Query persisted video hazard events."""
        from features.vision.video_pipeline import list_video_events
        return list_video_events(category, borough, min_duration_sec, limit)

    @app.get("/v1/video/events/timeline/{video_id}")
    def get_video_timeline(video_id: str) -> list[dict]:
        """Get chronological event timeline for a specific video."""
        from features.vision.video_pipeline import get_event_timeline
        return get_event_timeline(video_id)

    @app.get("/v1/video/events/{event_id}")
    def get_video_event_detail(event_id: str) -> dict:
        """Get full details for a single video event including bbox_history."""
        from features.vision.video_pipeline import VIDEO_DB
        import sqlite3
        if not VIDEO_DB.exists():
            return {"error": "No video events database"}
        with sqlite3.connect(VIDEO_DB) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM video_events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if not row:
                return {"error": "Event not found"}
            import json
            result = dict(row)
            try:
                result["bbox_history"] = json.loads(result.get("bbox_history", "[]"))
            except Exception:
                result["bbox_history"] = []
            return result

    @app.post("/v1/video/query")
    async def post_video_query(question: str = Query(..., min_length=1)) -> dict:
        """Natural language query over video events.

        Example: "Show flooding events longer than 5 seconds in Camden"
        """
        from features.vision.video_query import query_events
        return query_events(question)

    @app.get("/v1/geo/video-events")
    def get_video_events_geojson() -> dict:
        """Return GeoJSON FeatureCollection of all video hazard events for map rendering."""
        from features.vision.video_pipeline import VIDEO_GEOJSON
        import json
        if VIDEO_GEOJSON.exists():
            with VIDEO_GEOJSON.open("r", encoding="utf-8") as f:
                return json.load(f)
        return {"type": "FeatureCollection", "features": []}

    # --- Live TfL JamCam feed endpoints ---
    @app.post("/v1/livefeed/run")
    async def post_live_feed_run(
        camera_ids: list[str] | None = Query(None),
        snapshots_per_camera: int = Query(3, ge=1, le=10),
        snapshot_delay_sec: float = Query(5.0, ge=1.0, le=60.0),
    ) -> list[dict]:
        """Run one live feed monitoring cycle on TfL JamCams.

        Uses Nemotron Omni multimodal reasoning to analyze accessibility
        and mobility conditions from CCTV snapshots.
        """
        from features.vision.live_feed_pipeline import run_live_feed_cycle
        return await run_live_feed_cycle(
            camera_ids=camera_ids,
            snapshots_per_camera=snapshots_per_camera,
            snapshot_delay_sec=snapshot_delay_sec,
        )

    @app.get("/v1/livefeed/observations")
    def get_livefeed_observations(
        camera_id: str | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
    ) -> list[dict]:
        """Get latest live feed observations."""
        from features.vision.live_feed_pipeline import get_latest_observations
        return get_latest_observations(camera_id, limit)

    @app.get("/v1/livefeed/critical")
    def get_livefeed_critical(
        min_confidence: float = Query(0.6, ge=0.0, le=1.0),
    ) -> list[dict]:
        """Get critical observations (high crowd density, blocked access)."""
        from features.vision.live_feed_pipeline import get_critical_observations
        return get_critical_observations(min_confidence)

    @app.get("/v1/livefeed/cameras")
    async def get_livefeed_cameras(
        lat: float | None = Query(None),
        lon: float | None = Query(None),
        radius_km: float = Query(5.0, ge=0.1, le=50.0),
        limit: int = Query(50, ge=1, le=500),
        available_only: bool = Query(True),
    ) -> list[dict]:
        """Return TfL JamCam cameras with live image/video URLs.

        Optionally filters by geographic radius around a point.
        """
        import math
        from features.vision.live_feed_pipeline import fetch_jamcam_registry

        registry = await fetch_jamcam_registry()
        result = []
        for cam in registry:
            # Filter by availability if requested
            if available_only and cam.get("available") is False:
                continue
            # Geographic radius filter
            if lat is not None and lon is not None:
                c_lat = cam.get("lat")
                c_lon = cam.get("lon")
                if c_lat is not None and c_lon is not None:
                    # Haversine distance (approximate, km per degree lat ~111)
                    dx = (c_lon - lon) * 111.32 * math.cos(math.radians(lat))
                    dy = (c_lat - lat) * 111.32
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist > radius_km:
                        continue
            result.append(cam)
            if len(result) >= limit:
                break
        return result

    @app.get("/v1/livefeed/cameras/{camera_id}")
    async def get_livefeed_camera_detail(camera_id: str) -> dict:
        """Get single camera details including latest image/video URLs."""
        from features.vision.live_feed_pipeline import fetch_jamcam_registry
        registry = await fetch_jamcam_registry()
        for cam in registry:
            if cam["id"] == camera_id or cam["id"].endswith(camera_id):
                return cam
        raise HTTPException(status_code=404, detail="Camera not found")

    @app.post("/v1/livefeed/cameras/{camera_id}/analyze")
    async def analyze_camera_snapshot(
        camera_id: str,
        labels: list[str] | None = Query(None),
    ) -> dict:
        """Download a JamCam snapshot and run LocateAnything-3B object detection.

        Defaults to traffic labels (car, bus, person, etc.).
        Pass ?labels=blocked+pavement,broken+lift for hazard detection instead.
        """
        from features.vision.live_feed_pipeline import fetch_jamcam_registry, fetch_camera_snapshot
        from features.vision.locate_anything_client import get_client

        registry = await fetch_jamcam_registry()
        cam = None
        for c in registry:
            if c["id"] == camera_id or c["id"].endswith(camera_id):
                cam = c
                break
        if cam is None:
            raise HTTPException(status_code=404, detail="Camera not found")

        image_url = cam.get("image_url")
        if not image_url:
            raise HTTPException(status_code=404, detail="Camera has no image URL")

        image = await fetch_camera_snapshot(image_url)
        if image is None:
            raise HTTPException(status_code=502, detail="Failed to fetch camera snapshot")

        client = get_client()
        if labels is None:
            labels = ["car", "bus", "person", "bicycle", "truck", "van", "motorcycle"]
        detections = client.detect(image, labels, confidence_threshold=0.3)

        results = []
        for det in detections:
            results.append({
                "label": det.label,
                "bbox": det.bbox,
                "confidence": round(det.confidence, 3),
            })

        return {
            "camera_id": cam["id"],
            "camera_name": cam.get("name", cam["id"]),
            "image_url": image_url,
            "detections": results,
            "detection_count": len(results),
            "model": "LocateAnything-3B" if client.is_available() else "Nemotron-Omni-fallback",
        }

    @app.post("/v1/livefeed/cameras/{camera_id}/stream")
    async def analyze_camera_stream(
        camera_id: str,
        labels: list[str] | None = Query(None),
        sample_interval_sec: float = Query(2.0, ge=0.5, le=30.0),
        max_frames: int = Query(30, ge=1, le=120),
        temporal_smoothing: int = Query(3, ge=1, le=10),
    ) -> dict:
        """Poll a JamCam image URL repeatedly and run temporal video analysis.

        This endpoint treats the camera's snapshot URL as a pseudo-video stream,
        sampling frames at regular intervals and tracking objects temporally for
        more robust detection than a single snapshot.
        """
        from features.vision.live_feed_pipeline import fetch_jamcam_registry
        from features.vision.locate_anything_client import get_client

        registry = await fetch_jamcam_registry()
        cam = None
        for c in registry:
            if c["id"] == camera_id or c["id"].endswith(camera_id):
                cam = c
                break
        if cam is None:
            raise HTTPException(status_code=404, detail="Camera not found")

        image_url = cam.get("image_url")
        if not image_url:
            raise HTTPException(status_code=404, detail="Camera has no image URL")

        if labels is None:
            labels = ["car", "bus", "person", "bicycle", "truck", "van", "motorcycle"]

        client = get_client()
        result = client.detect_video_stream(
            image_url=image_url,
            labels=labels,
            sample_interval_sec=sample_interval_sec,
            max_frames=max_frames,
            confidence_threshold=0.3,
            temporal_smoothing=temporal_smoothing,
            iou_threshold=0.5,
        )

        return {
            "camera_id": cam["id"],
            "camera_name": cam.get("name", cam["id"]),
            "image_url": image_url,
            "stream_config": {
                "labels": labels,
                "sample_interval_sec": sample_interval_sec,
                "max_frames": max_frames,
                "temporal_smoothing": temporal_smoothing,
            },
            "detections": result.get("detections", []),
            "frame_count": result.get("frame_count", 0),
            "tracked_objects": result.get("tracked_objects", 0),
            "duration_sec": result.get("duration_sec", 0),
            "model": "LocateAnything-3B" if client.is_available() else "Nemotron-Omni-fallback",
        }

    @app.get("/v1/geo/live-observations")
    def get_live_observations_geojson() -> dict:
        """Return GeoJSON of latest live feed observations for map rendering."""
        from features.vision.live_feed_pipeline import LIVE_FEED_DB
        import json
        import sqlite3
        if not LIVE_FEED_DB.exists():
            return {"type": "FeatureCollection", "features": []}
        with sqlite3.connect(LIVE_FEED_DB) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM live_observations
                WHERE timestamp = (
                    SELECT MAX(timestamp) FROM live_observations AS sub
                    WHERE sub.camera_id = live_observations.camera_id
                )
                ORDER BY timestamp DESC
                """
            ).fetchall()
            features = []
            for row in rows:
                if row["lat"] is None or row["lon"] is None:
                    continue
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
                    "properties": {
                        "observation_id": row["observation_id"],
                        "camera_id": row["camera_id"],
                        "camera_name": row["camera_name"],
                        "crowd_density": row["crowd_density"],
                        "step_free_access": row["step_free_access"],
                        "platform_condition": row["platform_condition"],
                        "mobility_impact": row["mobility_impact"],
                        "confidence": row["confidence"],
                        "timestamp": row["timestamp"],
                    },
                })
        return {"type": "FeatureCollection", "features": features}

    # --- Audio ingestion endpoints ---
    @app.post("/v1/audio/analyze")
    async def upload_audio(
        audio: UploadFile = File(...),
        lat: float | None = Query(None),
        lon: float | None = Query(None),
        context_hint: str = Query("", max_length=200),
    ) -> dict:
        """Upload audio for Nemotron Omni environmental scene analysis.

        Accepts WAV, MP3, OGG, FLAC. Analyzes acoustic environment for
        crowd level, incidents, and accessibility-relevant sounds.
        """
        from features.vision.audio_pipeline import analyze_audio
        audio_bytes = await audio.read()
        return await analyze_audio(
            audio_bytes=audio_bytes,
            audio_format=audio.filename.split(".")[-1].lower() or "wav",
            lat=lat,
            lon=lon,
            source="upload",
            context_hint=context_hint,
        )

    @app.get("/v1/audio/observations")
    def get_audio_observations(
        limit: int = Query(50, ge=1, le=500),
        min_relevance: str | None = Query(None),
    ) -> list[dict]:
        """Get latest audio observations."""
        from features.vision.audio_pipeline import list_audio_observations
        return list_audio_observations(limit=limit, min_relevance=min_relevance)

    @app.get("/v1/audio/critical")
    def get_audio_critical() -> list[dict]:
        """Get high-priority audio observations (incidents, high relevance)."""
        from features.vision.audio_pipeline import get_high_priority_audio
        return get_high_priority_audio()

    @app.get("/v1/geo/audio-observations")
    def get_audio_observations_geojson() -> dict:
        """Return GeoJSON of audio observations for map rendering."""
        import json
        geojson_path = Path(__file__).resolve().parents[4] / "data" / "geo" / "audio_observations.geojson"
        if geojson_path.exists():
            with geojson_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        return {"type": "FeatureCollection", "features": []}

    # --- GPU-powered spatial endpoints ---
    @app.post("/v1/geo/hazards/cluster")
    async def post_hazard_cluster(
        eps_km: float = Query(0.2, ge=0.05, le=5.0),
        min_samples: int = Query(3, ge=2, le=50),
    ) -> dict:
        """DBSCAN cluster hazard points into hotspots.

        Args:
            eps_km: Neighborhood radius in km (default 200m).
            min_samples: Min points to form a cluster.

        GPU-accelerated when RAPIDS is available; CPU fallback otherwise.
        """
        from features.vision.hazard_pipeline import list_hazard_hotspots
        from shared.gpu.cuml_clustering import cluster_hazards

        records = list_hazard_hotspots(limit=1000)
        points: list[tuple[float, float]] = [
            (r["lat"], r["lon"])
            for r in records
            if r.get("lat") is not None and r.get("lon") is not None
        ]
        result = cluster_hazards(points, eps_km=eps_km, min_samples=min_samples)
        return {
            "cluster_count": result["cluster_count"],
            "noise_count": result["noise_count"],
            "hotspots": result["hotspots"],
            "total_points": len(points),
            "gpu_accelerated": False,  # Set by GPU layer
        }

    # --- Live TfL spatial helpers ---
    async def _tfl_nearby_stops(
        lat: float, lon: float, radius_m: int = 2000
    ) -> list[dict]:
        """Query TfL StopPoint search for stations near lat/lon."""
        import httpx
        import os

        base = "https://api.tfl.gov.uk"
        key = os.getenv("TFL_APP_KEY", "").strip()
        url = f"{base}/StopPoint"
        params: dict[str, str | int] = {
            "lat": lat,
            "lon": lon,
            "stopTypes": "NaptanMetroStation",
            "radius": radius_m,
            "modes": "tube,overground,dlr,elizabeth-line",
        }
        if key:
            params["app_key"] = key
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                stops = []
                for sp in data.get("stopPoints", []):
                    stops.append({
                        "stop_id": sp.get("id"),
                        "name": sp.get("commonName", sp.get("id")),
                        "lat": sp.get("lat"),
                        "lon": sp.get("lon"),
                        "modes": sp.get("modes", []),
                        "distance": sp.get("distance"),
                    })
                return stops
        except Exception as exc:
            logger.warning("tfl_nearby_stops failed: %s", exc)
            return []

    async def _tfl_stop_accessibility(stop_id: str) -> dict:
        """Fetch TfL StopPoint details and parse accessibility facilities."""
        import httpx
        import os

        base = "https://api.tfl.gov.uk"
        key = os.getenv("TFL_APP_KEY", "").strip()
        url = f"{base}/StopPoint/{stop_id}"
        params: dict[str, str] = {"app_key": key} if key else {}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                facilities = {
                    p.get("key", "").lower().replace(" ", "_"): p.get("value")
                    for p in data.get("additionalProperties", [])
                }
                has_lift = bool(facilities.get("lift", "") == "Yes")
                has_ramp = bool(facilities.get("boarding_ramp", "") == "Yes")
                step_free = has_lift or has_ramp or bool(facilities.get("step_free_access", "") == "Yes")
                return {
                    "stop_id": stop_id,
                    "name": data.get("commonName", stop_id),
                    "lat": data.get("lat"),
                    "lon": data.get("lon"),
                    "has_lift": has_lift,
                    "has_ramp": has_ramp,
                    "step_free": step_free,
                    "facilities": facilities,
                }
        except Exception as exc:
            logger.warning("tfl_stop_accessibility failed for %s: %s", stop_id, exc)
            return {"stop_id": stop_id, "step_free": False}

    @app.get("/v1/geo/nearest-step-free")
    async def get_nearest_step_free(
        lat: float = Query(..., ge=-90, le=90),
        lon: float = Query(..., ge=-180, le=180),
        max_km: float = Query(2.0, ge=0.1, le=10.0),
    ) -> dict:
        """Find nearest step-free station to a lat/lon using live TfL data.

        Returns station dict or empty if none within max_km.
        """
        from shared.gpu.cuspatial_join import haversine_km

        stops = await _tfl_nearby_stops(lat, lon, radius_m=int(max_km * 1000))
        if not stops:
            return {"found": False, "station": None, "source": "tfl_api"}

        # Check accessibility for each nearby stop
        step_free_stops: list[dict] = []
        for sp in stops:
            acc = await _tfl_stop_accessibility(sp["stop_id"])
            if acc.get("step_free"):
                step_free_stops.append({**sp, **acc})

        if not step_free_stops:
            return {"found": False, "station": None, "source": "tfl_api"}

        # Pick nearest by haversine
        nearest = min(
            step_free_stops,
            key=lambda s: haversine_km(lat, lon, s["lat"], s["lon"]),
        )
        dist = haversine_km(lat, lon, nearest["lat"], nearest["lon"])
        return {
            "found": True,
            "station": nearest,
            "distance_km": round(dist, 3),
            "source": "tfl_api",
        }

    @app.get("/v1/geo/accessibility-risk")
    async def get_accessibility_risk(
        lat: float = Query(..., ge=-90, le=90),
        lon: float = Query(..., ge=-180, le=180),
        line_id: str | None = Query(None),
    ) -> dict:
        """Composite accessibility risk snapshot for a location.

        Combines: ward info, nearest step-free station distance,
        nearby reported hazards from SQLite, and optional line-level disruption.
        """
        from features.vision.hazard_pipeline import _resolve_ward, list_hazard_hotspots
        from shared.gpu.cuspatial_join import haversine_km

        ward_info = _resolve_ward(lat, lon)
        nearest = await get_nearest_step_free(lat, lon, max_km=5.0)

        # Query actual SQLite hazards within 1km radius
        nearby_hazards: list[dict] = []
        try:
            all_hazards = list_hazard_hotspots(limit=1000)
            for h in all_hazards:
                hlat = h.get("lat")
                hlon = h.get("lon")
                if hlat is not None and hlon is not None:
                    d = haversine_km(lat, lon, hlat, hlon)
                    if d <= 1.0:
                        nearby_hazards.append({**h, "distance_km": round(d, 3)})
        except Exception as exc:
            logger.warning("hazard lookup failed: %s", exc)

        risk_score = 0.0
        factors: list[str] = []

        if ward_info:
            risk_score += 0.1
            factors.append(f"Ward: {ward_info.get('ward')}")

        if nearest.get("found"):
            dist_km = nearest.get("distance_km", 5.0)
            risk_score += min(dist_km / 5.0, 1.0)
            station = nearest["station"]
            factors.append(
                f"Nearest step-free: {station.get('name')} ({dist_km} km)"
            )
        else:
            risk_score += 1.0
            factors.append("No step-free station within 5 km")

        if nearby_hazards:
            risk_score += min(len(nearby_hazards) * 0.2, 1.0)
            factors.append(f"Nearby hazards reported: {len(nearby_hazards)}")

        if line_id:
            factors.append(f"Line checked: {line_id}")

        return {
            "lat": lat,
            "lon": lon,
            "ward": ward_info,
            "nearest_step_free": nearest.get("station") if nearest.get("found") else None,
            "nearby_hazards": nearby_hazards,
            "risk_score": round(min(risk_score, 2.0), 2),
            "factors": factors,
            "source": "tfl_api + sqlite",
        }

    # --- TfL road disruption endpoint ---
    @app.get("/v1/geo/road-disruptions")
    async def get_road_disruptions(
        severity: str = Query("all"),
        limit: int = Query(20, ge=1, le=50),
    ) -> dict:
        """Fetch live road disruptions from TfL API."""
        import httpx
        import os

        base = "https://api.tfl.gov.uk"
        key = os.getenv("TFL_APP_KEY", "").strip()
        url = f"{base}/Road/All/Disruption"
        params: dict[str, str | int] = {}
        if key:
            params["app_key"] = key
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                disruptions = []
                for d in data:
                    sev = d.get("severity", "").lower()
                    if severity != "all" and sev != severity.lower():
                        continue
                    disruptions.append({
                        "street": d.get("streetName", "Unknown"),
                        "description": d.get("description", ""),
                        "severity": d.get("severity", ""),
                        "category": d.get("category", ""),
                        "start": d.get("startDate", "")[:10],
                        "end": d.get("endDate", "")[:10],
                        "lat": d.get("lat"),
                        "lon": d.get("lon"),
                    })
                    if len(disruptions) >= limit:
                        break
                return {"disruptions": disruptions, "count": len(disruptions), "source": "tfl_api"}
        except Exception as exc:
            logger.warning("tfl road disruptions failed: %s", exc)
            return {"disruptions": [], "count": 0, "source": "tfl_api", "error": str(exc)}

    # --- NVIDIA cuOpt VRP for hazard-response crew routing ---
    @app.post("/v1/routing/hazard-response")
    async def plan_hazard_response_routes_endpoint(
        hazard_ids: list[str] | None = Query(None),
        max_vehicles: int = Query(3, ge=1, le=10),
        vehicle_capacity: int = Query(5, ge=1, le=20),
    ) -> dict:
        """Plan optimal crew dispatch routes from depots to hazards using NVIDIA cuOpt VRP.

        Reads open hazards from the hazard database + known London response depots
        and returns ordered waypoints per vehicle. Falls back to greedy nearest-
        neighbour if cuOpt is unavailable.
        """
        from platform.shared.gpu.cuopt_routing import plan_hazard_response_routes

        ids = None
        if hazard_ids:
            try:
                ids = [int(h) for h in hazard_ids]
            except ValueError:
                raise HTTPException(status_code=400, detail="hazard_ids must be integers")

        result = plan_hazard_response_routes(
            hazard_ids=ids,
            max_vehicles=max_vehicles,
            vehicle_capacity=vehicle_capacity,
        )
        return result

    @app.get("/v1/routing/depots")
    def list_response_depots() -> list[dict]:
        """Return known London response depot locations for VRP routing."""
        from platform.shared.gpu.cuopt_routing import _load_depots
        depots = _load_depots()
        return depots

    # --- NVIDIA RAG (NeMo Retriever style) endpoints ---
    @app.post("/v1/rag/query")
    async def rag_query(
        query: str = Query(..., min_length=1, max_length=8000),
        top_k: int = Query(5, ge=1, le=20),
    ) -> dict:
        """Query the RAG knowledge base for London mobility/accessibility info.

        Uses GPU-accelerated vector search (cuVS) when available,
        falling back to FAISS-CPU or brute-force.
        """
        from platform.shared.gpu.rag_engine import get_rag_engine

        engine = get_rag_engine()
        engine.top_k = top_k
        return engine.query(query)

    @app.post("/v1/rag/ingest")
    async def rag_ingest(body: list[dict]) -> dict:
        """Ingest documents into the RAG vector store.

        Body: list of {"text": "...", "source": "...", "metadata": {}} objects.
        """
        from platform.shared.gpu.rag_engine import get_rag_engine

        engine = get_rag_engine()
        engine.add_documents(body)
        return {"status": "ingested", "count": len(body)}

    @app.get("/v1/rag/stats")
    def rag_stats() -> dict:
        """Return RAG index statistics."""
        import sqlite3
        from platform.shared.gpu.rag_engine import RAG_DB, GPU_VS_AVAILABLE, FAISS_AVAILABLE

        chunk_count = 0
        query_count = 0
        if RAG_DB.exists():
            with sqlite3.connect(RAG_DB) as conn:
                row = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
                chunk_count = row[0] if row else 0
                row = conn.execute("SELECT COUNT(*) FROM queries").fetchone()
                query_count = row[0] if row else 0

        return {
            "chunks": chunk_count,
            "queries": query_count,
            "gpu_accelerated": GPU_VS_AVAILABLE,
            "gpu_backend": "cuVS (RAPIDS CAGRA)" if GPU_VS_AVAILABLE else ("FAISS" if FAISS_AVAILABLE else "brute-force"),
            "embedding_model": "llama-nemotron-embed",
        }

    # --- NVIDIA Cosmos Reason 2 video reasoning endpoint ---
    @app.post("/v1/vision/cosmos-reason")
    async def cosmos_reason_clip(
        video: UploadFile = File(...),
        question: str = Query("Describe what is happening in this video clip."),
    ) -> dict:
        """Run Cosmos Reason 2 video reasoning on a CCTV clip.

        Upload a short MP4 clip (5-15 seconds) for causal video analysis:
        crowd formation, flooding progression, accident causation, etc.
        Falls back to Nemotron Omni on first frame if Cosmos unavailable.
        """
        from platform.shared.gpu.cosmos_reason import get_cosmos_client
        import tempfile

        suffix = Path(video.filename).suffix or ".mp4"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await video.read())
            tmp_path = tmp.name

        client = get_cosmos_client()
        result = client.analyze_clip(tmp_path, question=question)
        Path(tmp_path).unlink(missing_ok=True)
        return result

    # --- NVIDIA Riva voice (ASR + TTS) endpoints ---
    @app.post("/v1/voice/transcribe")
    async def riva_transcribe(
        audio: UploadFile = File(...),
        sample_rate: int = Query(16000),
    ) -> dict:
        """ASR: Transcribe uploaded audio using Riva NIM (privacy-first, local)."""
        from platform.shared.gpu.riva_voice import get_riva_client

        client = get_riva_client()
        audio_bytes = await audio.read()
        return client.transcribe(audio_bytes, sample_rate=sample_rate)

    @app.post("/v1/voice/synthesize")
    async def riva_synthesize(
        text: str = Query(..., min_length=1, max_length=2000),
        voice: str = Query("English-GB.Female"),
        severity: str = Query("info"),
    ) -> dict:
        """TTS: Synthesize speech from text using Riva NIM.

        PII is automatically stripped before synthesis.
        Severity controls voice persona (info/warning/critical).
        """
        from platform.shared.gpu.riva_voice import get_riva_client

        client = get_riva_client()
        if severity in ("warning", "critical"):
            return client.synthesize_alert(text, severity=severity)
        return client.synthesize(text, voice=voice)

    @app.get("/v1/voice/status")
    def riva_status() -> dict:
        """Check Riva ASR + TTS NIM availability."""
        from platform.shared.gpu.riva_voice import get_riva_client

        client = get_riva_client()
        return {
            **client.is_available(),
            "note": "Self-hosted Riva NIM for zero-cloud voice privacy.",
        }

    # --- NeMo Agent Toolkit (NAT) orchestration endpoints ---
    @app.post("/v1/agent/workflow")
    async def agent_run_workflow(
        workflow: str = Query(..., description="hazard_response | accessibility_query | live_monitor"),
        camera_id: str | None = Query(None),
        labels: list[str] | None = Query(None),
        query: str | None = Query(None),
        video_path: str | None = Query(None),
        question: str | None = Query(None),
    ) -> dict:
        """Run a multi-step agent workflow with full profiling and fallback chains.

        Workflows:
        - hazard_response: detect → route → alert
        - accessibility_query: rag → voice response
        - live_monitor: detect + cosmos reason loop
        """
        from platform.shared.gpu.nat_orchestrator import get_nat_orchestrator

        nat = get_nat_orchestrator()
        inputs = {
            "camera_id": camera_id,
            "labels": labels or ["flooding", "pavement_obstruction"],
            "query": query,
            "video_path": video_path,
            "question": question,
        }
        # Filter out None values
        inputs = {k: v for k, v in inputs.items() if v is not None}
        return nat.run_workflow(workflow, inputs)

    @app.get("/v1/agent/traces")
    def agent_get_traces(
        limit: int = Query(100, ge=1, le=1000),
    ) -> list[dict]:
        """Return recent agent workflow traces with latency + GPU memory."""
        from platform.shared.gpu.nat_orchestrator import get_nat_orchestrator

        nat = get_nat_orchestrator()
        return nat.get_traces(limit=limit)

    @app.get("/v1/agent/tools")
    def agent_list_tools() -> dict:
        """List registered NAT tools and fallback chains."""
        from platform.shared.gpu.nat_orchestrator import get_nat_orchestrator

        nat = get_nat_orchestrator()
        return {
            "tools": list(nat.tool_registry.keys()),
            "fallback_chains": nat.fallback_chains,
        }

    return app
