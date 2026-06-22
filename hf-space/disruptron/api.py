from __future__ import annotations

import io
import json
import logging
import os
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from disruptron.agent import AgentChatEngine, AgentTurn

logger = logging.getLogger(__name__)

VLLM_URL = os.environ.get("VLLM_URL", "http://127.0.0.1:8000/v1")
VLLM_MODEL = os.environ.get("VLLM_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16")
TFL_APP_KEY = os.environ.get("TFL_APP_KEY", "")
LOCATEANYTHING_MODEL = os.environ.get("LOCATEANYTHING_MODEL", "nvidia/LocateAnything-3B")
GITHUB_PAGES_ORIGINS = [
    "https://ryukijano.github.io",
    "https://ryukijano.github.io/NV-Disruptron",
    "https://ryukijano.github.io/NV-Disruptron/",
]


def _tfl_params() -> dict:
    return {"app_key": TFL_APP_KEY} if TFL_APP_KEY else {}


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096)
    session_id: str = Field("web-user", max_length=128)
    stream: bool = False


class ChatResponse(BaseModel):
    reply: str
    tool_kinds: list[str]


class VisionDetectRequest(BaseModel):
    image_url: str = Field(..., min_length=1, max_length=2048)
    labels: list[str] = Field(..., min_length=1)
    confidence_threshold: float = Field(0.3, ge=0.0, le=1.0)


class VisionDetectResponse(BaseModel):
    detections: list[dict]
    model: str
    used_fallback: bool


class WebChatStreamRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    session_id: str | None = Field(None, max_length=128)
    user_id: str | None = Field(None, max_length=128)
    image_path: str | None = Field(None, max_length=512)


class WebSessionCreateRequest(BaseModel):
    session_id: str | None = Field(None, max_length=128)
    user_id: str | None = Field(None, max_length=128)


class ChatMessageItem(BaseModel):
    id: str
    role: str
    text: str


class WebChatResponse(BaseModel):
    reply: str


class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=480)


class TranscribeResponse(BaseModel):
    text: str


class WebSummaryItem(BaseModel):
    date: str
    title: str
    body: str
    updated_at: int


class WebSummaryUpsertRequest(BaseModel):
    session_id: str
    date: str
    title: str
    body: str


class WebNotificationItem(BaseModel):
    id: str
    title: str
    body: str
    kind: str
    timestamp: int


class WebNotificationCreateRequest(BaseModel):
    session_id: str
    title: str
    body: str = ""
    kind: str = "info"
    id: str | None = None


class WebSubscriptionResponse(BaseModel):
    session_id: str
    alerts: bool
    daily: bool


class WebSubscriptionUpdateRequest(BaseModel):
    session_id: str
    alerts: bool
    daily: bool


class UserPreferences(BaseModel):
    tube_lines: list[str] = []
    areas: list[str] = []
    ev_enabled: bool = False
    commute_morning: str = ""
    commute_evening: str = ""
    onboarding_complete: bool = False


class WebPreferencesRequest(BaseModel):
    session_id: str
    tube_lines: list[str] | None = None
    areas: list[str] | None = None
    ev_enabled: bool | None = None
    commute_morning: str | None = None
    commute_evening: str | None = None
    onboarding_complete: bool | None = None


class WebPreferencesResponse(BaseModel):
    session_id: str
    tube_lines: list[str]
    areas: list[str]
    ev_enabled: bool
    commute_morning: str
    commute_evening: str
    onboarding_complete: bool


class WebSessionBootstrapResponse(BaseModel):
    session_id: str
    messages: list[dict]
    summaries: list[WebSummaryItem]
    notifications: list[WebNotificationItem]
    subscriptions: WebSubscriptionResponse


def _web_db_path() -> Path:
    return Path(os.environ.get("DISRUPTRON_WEB_DB", "/tmp/disruptron_web.db"))


def _init_web_db() -> None:
    path = _web_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS web_subscriptions (
            session_id TEXT PRIMARY KEY,
            alerts INTEGER DEFAULT 0,
            daily INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS web_preferences (
            session_id TEXT PRIMARY KEY,
            tube_lines TEXT DEFAULT '[]',
            areas TEXT DEFAULT '[]',
            ev_enabled INTEGER DEFAULT 0,
            commute_morning TEXT DEFAULT '',
            commute_evening TEXT DEFAULT '',
            onboarding_complete INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS web_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            date TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            updated_at INTEGER NOT NULL,
            UNIQUE(session_id, date)
        );
        CREATE TABLE IF NOT EXISTS web_notifications (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            kind TEXT NOT NULL,
            timestamp INTEGER NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _get_db() -> sqlite3.Connection:
    return sqlite3.connect(str(_web_db_path()))


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(timeout=httpx.Timeout(300.0))
    app.state.agent = AgentChatEngine(model_url=VLLM_URL, model_name=VLLM_MODEL)
    # Vision client loads lazily on first request to avoid slow startup
    app.state.vision_client = None
    _init_web_db()
    yield
    await app.state.client.aclose()


app = FastAPI(
    title="NV-Disruptron HF Space API",
    description="Lightweight demo backend for the NV-Disruptron GitHub Pages frontend.",
    version="0.2.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=GITHUB_PAGES_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "service": "nv-disruptron-hf"}


@app.get("/api/v1/integrations")
async def integrations() -> dict:
    vision_client = getattr(app.state, "vision_client", None)
    vision_ready = bool(vision_client and vision_client.is_available())
    return {
        "telegram": {
            "mode": "disabled",
            "recommended": "web",
            "description": "Telegram delivery is not configured in this HF Space demo.",
            "warning": "Configure a bot token to enable Telegram alerts.",
        },
        "calendar": {},
        "tfl_journey": {"enabled": True, "source": "tfl_api", "status": "ready"},
        "elevenlabs": {"enabled": False, "status": "not_configured"},
        "nemotron": {"enabled": True, "status": "healthy", "url": VLLM_URL, "model": VLLM_MODEL},
        "locateanything": {
            "cached": vision_ready,
            "status": "cached" if vision_ready else "unavailable",
            "model": LOCATEANYTHING_MODEL,
            "message": "LocateAnything-3B vision model loaded" if vision_ready else "Vision model not loaded",
        },
        "gpu": {"available": True, "model": VLLM_MODEL, "status": "ready"},
        "vision": {"available": vision_ready},
        "scheduler": {"enabled": False, "daily_digest": "08:00"},
        "agent": {
            "local": True,
            "chat_mode": "interactive",
            "interactive_agent_id": "disruptron",
            "autonomous_agent_id": "disruptron",
            "timeout_s": 120,
        },
        "version": "0.2.0",
    }


@app.post("/api/v1/vision/detect", response_model=VisionDetectResponse)
async def vision_detect(req: VisionDetectRequest) -> VisionDetectResponse:
    try:
        from PIL import Image

        vision_client = getattr(app.state, "vision_client", None)
        if vision_client is None:
            try:
                from disruptron.vision import get_vision_client
                vision_client = get_vision_client()
                app.state.vision_client = vision_client
            except Exception:
                raise HTTPException(status_code=503, detail="Vision model not available")

        resp = await app.state.client.get(req.image_url, timeout=20.0)
        resp.raise_for_status()
        image = Image.open(io.BytesIO(resp.content)).convert("RGB")
        detections = vision_client.detect(
            image, req.labels, confidence_threshold=req.confidence_threshold
        )
        return VisionDetectResponse(
            detections=[
                {"label": d.label, "bbox": d.bbox, "confidence": d.confidence}
                for d in detections
            ],
            model=LOCATEANYTHING_MODEL,
            used_fallback=not vision_client.is_available(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("vision detect failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    try:
        result = await app.state.agent.ask(
            AgentTurn(channel="web", chat_id=req.session_id, text=req.message)
        )
        return ChatResponse(reply=result.reply, tool_kinds=result.tool_kinds)
    except Exception as exc:
        logger.exception("chat failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def _london_snapshot() -> dict:
    """Fetch a concise live London snapshot from TfL APIs."""
    snapshot: dict[str, Any] = {}
    try:
        resp = await app.state.client.get(
            "https://api.tfl.gov.uk/Line/Mode/tube,overground,dlr,elizabeth-line/Status",
            params=_tfl_params(), timeout=15.0
        )
        resp.raise_for_status()
        lines = []
        for line in resp.json():
            status = line.get("lineStatuses", [{}])[0].get("statusSeverityDescription", "Good")
            if status not in ("Good Service", "No Step-free Access"):
                lines.append(f"{line.get('name', 'Unknown')}: {status}")
        snapshot["lines"] = lines
    except Exception as exc:
        logger.warning("london line status fetch failed: %s", exc)
        snapshot["lines"] = []
    try:
        resp = await app.state.client.get(
            "https://api.tfl.gov.uk/Road/All/Disruption",
            params=_tfl_params(), timeout=15.0
        )
        resp.raise_for_status()
        disruptions = resp.json()
        snapshot["roads"] = [
            f"{d.get('roadName', 'Road')}: {d.get('status', 'Disruption')}"
            for d in disruptions[:5]
        ]
    except Exception as exc:
        logger.warning("london road disruption fetch failed: %s", exc)
        snapshot["roads"] = []
    return snapshot


def _looks_like_london_query(text: str) -> bool:
    keywords = [
        "london", "tube", "tfl", "transport", "traffic", "road", "congestion",
        "jubilee", "piccadilly", "central", "district", "northern", "circle",
        "metropolitan", "bakerloo", "victoria", "hammersmith", "elizabeth",
        "overground", "dlr", "tram", "bus", "strike", "delay", "disruption",
    ]
    lowered = text.lower()
    return any(k in lowered for k in keywords)


@app.post("/api/v1/chat/stream")
async def chat_stream(req: WebChatStreamRequest) -> StreamingResponse:
    session_id = req.session_id or "web-default"

    async def _stream() -> Any:
        try:
            yield f"data: {json.dumps({'type': 'status', 'text': 'Checking London feeds…'})}\n\n"

            system_content = _system_prompt()
            if _looks_like_london_query(req.text):
                snapshot = await _london_snapshot()
                lines = "; ".join(snapshot.get("lines", [])) or "All lines reported good service"
                roads = "; ".join(snapshot.get("roads", [])) or "No major road disruptions"
                system_content += (
                    f"\n\nLive TfL snapshot (use this if relevant):\n"
                    f"Tube/Overground/DLR/Elizabeth line: {lines}\n"
                    f"Road disruptions: {roads}"
                )
                yield f"data: {json.dumps({'type': 'status', 'text': 'Live data loaded'})}\n\n"

            payload = {
                "model": VLLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": req.text},
                ],
                "stream": True,
                "max_tokens": 512,
                "temperature": 0.7,
            }
            reply = ""
            async with app.state.client.stream(
                "POST", f"{VLLM_URL}/chat/completions", json=payload, timeout=120.0
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta:
                            reply += delta
                    except Exception:
                        continue
            yield f"data: {json.dumps({'type': 'done', 'reply': reply.strip()})}\n\n"
        except httpx.ConnectError:
            logger.warning("vLLM not reachable; returning fallback response")
            fallback = "NV-Disruptron is warming up the LLM backend. "
            if _looks_like_london_query(req.text):
                snapshot = await _london_snapshot()
                lines = "; ".join(snapshot.get("lines", [])) or "All lines reported good service"
                roads = "; ".join(snapshot.get("roads", [])) or "No major road disruptions"
                fallback = f"Live London update:\nTube/Overground/DLR/Elizabeth: {lines}\nRoad disruptions: {roads}"
            yield f"data: {json.dumps({'type': 'done', 'reply': fallback})}\n\n"
        except Exception as exc:
            logger.exception("stream failed")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@app.post("/api/v1/chat/image", response_model=WebChatResponse)
async def chat_image(
    text: str = Query(...), session_id: str = Query("web-default"), image: UploadFile = File(...)
) -> WebChatResponse:
    try:
        contents = await image.read()
        # Image chat is not fully wired in this lightweight HF Space backend; fall back to text model
        result = await app.state.agent.ask(
            AgentTurn(channel="web", chat_id=session_id, text=f"[User uploaded an image] {text}")
        )
        return WebChatResponse(reply=result.reply)
    except Exception as exc:
        logger.exception("image chat failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/v1/transcribe", response_model=TranscribeResponse)
async def transcribe(audio: UploadFile = File(...)) -> TranscribeResponse:
    # Transcription is not wired in this lightweight backend; return a graceful placeholder
    logger.warning("transcribe called but STT is not configured in HF Space demo")
    return TranscribeResponse(text="(Voice transcription is not enabled in this demo space.)")


@app.post("/api/v1/tts")
async def tts(req: TtsRequest) -> StreamingResponse:
    # TTS is not wired in this lightweight backend; return an empty audio placeholder
    logger.warning("tts called but ElevenLabs is not configured in HF Space demo")
    return StreamingResponse(
        io.BytesIO(b""), media_type="audio/mpeg", headers={"Content-Disposition": "attachment; filename=tts.mp3"}
    )


@app.post("/api/v1/web/session", response_model=WebSessionBootstrapResponse)
async def web_session_create(req: WebSessionCreateRequest) -> WebSessionBootstrapResponse:
    session_id = req.session_id or f"web-{uuid.uuid4().hex[:12]}"
    return await _bootstrap_session(session_id)


@app.get("/api/v1/web/bootstrap", response_model=WebSessionBootstrapResponse)
async def web_bootstrap(session_id: str = Query(..., min_length=4)) -> WebSessionBootstrapResponse:
    return await _bootstrap_session(session_id)


async def _bootstrap_session(session_id: str) -> WebSessionBootstrapResponse:
    conn = _get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT date, title, body, updated_at FROM web_summaries WHERE session_id = ? ORDER BY updated_at DESC LIMIT 20",
        (session_id,),
    )
    summaries = [WebSummaryItem(date=r[0], title=r[1], body=r[2], updated_at=r[3]) for r in cur.fetchall()]
    cur.execute(
        "SELECT id, title, body, kind, timestamp FROM web_notifications WHERE session_id = ? ORDER BY timestamp DESC LIMIT 20",
        (session_id,),
    )
    notifications = [
        WebNotificationItem(id=r[0], title=r[1], body=r[2], kind=r[3], timestamp=r[4]) for r in cur.fetchall()
    ]
    cur.execute("INSERT OR IGNORE INTO web_subscriptions (session_id) VALUES (?)", (session_id,))
    cur.execute("SELECT session_id, alerts, daily FROM web_subscriptions WHERE session_id = ?", (session_id,))
    row = cur.fetchone()
    subscriptions = WebSubscriptionResponse(session_id=row[0], alerts=bool(row[1]), daily=bool(row[2]))
    conn.commit()
    conn.close()
    return WebSessionBootstrapResponse(
        session_id=session_id,
        messages=[],
        summaries=summaries,
        notifications=notifications,
        subscriptions=subscriptions,
    )


@app.get("/api/v1/web/messages", response_model=list[ChatMessageItem])
async def web_messages(session_id: str = Query(..., min_length=4), limit: int = Query(100, ge=1, le=500)) -> list[ChatMessageItem]:
    return []


@app.get("/api/v1/web/subscriptions", response_model=WebSubscriptionResponse)
async def get_web_subscriptions(session_id: str = Query(..., min_length=4)) -> WebSubscriptionResponse:
    conn = _get_db()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO web_subscriptions (session_id) VALUES (?)", (session_id,))
    cur.execute("SELECT session_id, alerts, daily FROM web_subscriptions WHERE session_id = ?", (session_id,))
    row = cur.fetchone()
    conn.commit()
    conn.close()
    return WebSubscriptionResponse(session_id=row[0], alerts=bool(row[1]), daily=bool(row[2]))


@app.put("/api/v1/web/subscriptions", response_model=WebSubscriptionResponse)
async def put_web_subscriptions(req: WebSubscriptionUpdateRequest) -> WebSubscriptionResponse:
    conn = _get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO web_subscriptions (session_id, alerts, daily) VALUES (?, ?, ?) "
        "ON CONFLICT(session_id) DO UPDATE SET alerts=excluded.alerts, daily=excluded.daily",
        (req.session_id, int(req.alerts), int(req.daily)),
    )
    conn.commit()
    conn.close()
    return WebSubscriptionResponse(session_id=req.session_id, alerts=req.alerts, daily=req.daily)


@app.get("/api/v1/web/summaries", response_model=list[WebSummaryItem])
async def get_web_summaries(
    session_id: str = Query(..., min_length=4), limit: int = Query(20, ge=1, le=100)
) -> list[WebSummaryItem]:
    conn = _get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT date, title, body, updated_at FROM web_summaries WHERE session_id = ? ORDER BY updated_at DESC LIMIT ?",
        (session_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return [WebSummaryItem(date=r[0], title=r[1], body=r[2], updated_at=r[3]) for r in rows]


@app.put("/api/v1/web/summaries", response_model=WebSummaryItem)
async def put_web_summary(req: WebSummaryUpsertRequest) -> WebSummaryItem:
    now = _now_ms()
    conn = _get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO web_summaries (session_id, date, title, body, updated_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(session_id, date) DO UPDATE SET title=excluded.title, body=excluded.body, updated_at=excluded.updated_at",
        (req.session_id, req.date, req.title, req.body, now),
    )
    conn.commit()
    conn.close()
    return WebSummaryItem(date=req.date, title=req.title, body=req.body, updated_at=now)


@app.get("/api/v1/web/notifications", response_model=list[WebNotificationItem])
async def get_web_notifications(
    session_id: str = Query(..., min_length=4), limit: int = Query(100, ge=1, le=200)
) -> list[WebNotificationItem]:
    conn = _get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, body, kind, timestamp FROM web_notifications WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
        (session_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return [WebNotificationItem(id=r[0], title=r[1], body=r[2], kind=r[3], timestamp=r[4]) for r in rows]


@app.post("/api/v1/web/notifications", response_model=WebNotificationItem)
async def post_web_notification(req: WebNotificationCreateRequest) -> WebNotificationItem:
    now = _now_ms()
    nid = req.id or str(uuid.uuid4())
    conn = _get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO web_notifications (id, session_id, title, body, kind, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (nid, req.session_id, req.title, req.body, req.kind, now),
    )
    conn.commit()
    conn.close()
    return WebNotificationItem(id=nid, title=req.title, body=req.body, kind=req.kind, timestamp=now)


@app.get("/api/v1/web/preferences", response_model=WebPreferencesResponse)
async def get_web_preferences(session_id: str = Query(..., min_length=4)) -> WebPreferencesResponse:
    conn = _get_db()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO web_preferences (session_id) VALUES (?)", (session_id,))
    cur.execute(
        "SELECT tube_lines, areas, ev_enabled, commute_morning, commute_evening, onboarding_complete "
        "FROM web_preferences WHERE session_id = ?",
        (session_id,),
    )
    row = cur.fetchone()
    conn.commit()
    conn.close()
    return WebPreferencesResponse(
        session_id=session_id,
        tube_lines=json.loads(row[0]),
        areas=json.loads(row[1]),
        ev_enabled=bool(row[2]),
        commute_morning=row[3],
        commute_evening=row[4],
        onboarding_complete=bool(row[5]),
    )


@app.put("/api/v1/web/preferences", response_model=WebPreferencesResponse)
async def put_web_preferences(req: WebPreferencesRequest) -> WebPreferencesResponse:
    existing = await get_web_preferences(req.session_id)
    prefs = UserPreferences(
        tube_lines=req.tube_lines if req.tube_lines is not None else existing.tube_lines,
        areas=req.areas if req.areas is not None else existing.areas,
        ev_enabled=req.ev_enabled if req.ev_enabled is not None else existing.ev_enabled,
        commute_morning=req.commute_morning if req.commute_morning is not None else existing.commute_morning,
        commute_evening=req.commute_evening if req.commute_evening is not None else existing.commute_evening,
        onboarding_complete=req.onboarding_complete if req.onboarding_complete is not None else existing.onboarding_complete,
    )
    conn = _get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO web_preferences (session_id, tube_lines, areas, ev_enabled, commute_morning, commute_evening, onboarding_complete) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(session_id) DO UPDATE SET tube_lines=excluded.tube_lines, areas=excluded.areas, "
        "ev_enabled=excluded.ev_enabled, commute_morning=excluded.commute_morning, "
        "commute_evening=excluded.commute_evening, onboarding_complete=excluded.onboarding_complete",
        (
            req.session_id,
            json.dumps(prefs.tube_lines),
            json.dumps(prefs.areas),
            int(prefs.ev_enabled),
            prefs.commute_morning,
            prefs.commute_evening,
            int(prefs.onboarding_complete),
        ),
    )
    conn.commit()
    conn.close()
    return WebPreferencesResponse(session_id=req.session_id, **prefs.model_dump())


@app.get("/api/v1/geo/road-congestion")
async def road_congestion(bbox: str | None = Query(None)) -> dict:
    url = "https://api.tfl.gov.uk/Road/All/Disruption"
    try:
        resp = await app.state.client.get(url, params=_tfl_params(), timeout=20.0)
        resp.raise_for_status()
        data = resp.json()
        return {"type": "FeatureCollection", "features": data}
    except Exception as exc:
        logger.warning("tfl road disruption failed: %s", exc)
        return {"type": "FeatureCollection", "features": [], "error": str(exc)}


@app.get("/api/v1/geo/line-status")
async def line_status() -> dict:
    url = "https://api.tfl.gov.uk/Line/Mode/tube,overground,dlr,elizabeth-line/Status"
    try:
        resp = await app.state.client.get(url, params=_tfl_params(), timeout=20.0)
        resp.raise_for_status()
        return {"lines": resp.json()}
    except Exception as exc:
        logger.warning("tfl line status failed: %s", exc)
        return {"lines": [], "error": str(exc)}


@app.get("/api/v1/cameras")
async def cameras() -> dict:
    url = "https://api.tfl.gov.uk/Place/Type/JamCam"
    try:
        resp = await app.state.client.get(url, params=_tfl_params(), timeout=20.0)
        resp.raise_for_status()
        return {"cameras": resp.json()}
    except Exception as exc:
        logger.warning("tfl cameras failed: %s", exc)
        return {"cameras": [], "error": str(exc)}


def _system_prompt() -> str:
    return (
        "You are NV-Disruptron, a helpful AI assistant for London mobility and transport. "
        "You answer concisely about TfL disruptions, road congestion, and accessibility. "
        "If you lack live data, say so and suggest what to check."
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("FASTAPI_PORT", "8010")))
