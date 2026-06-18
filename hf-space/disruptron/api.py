from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from disruptron.agent import AgentChatEngine, AgentTurn

logger = logging.getLogger(__name__)

VLLM_URL = os.environ.get("VLLM_URL", "http://127.0.0.1:8000/v1")
VLLM_MODEL = os.environ.get("VLLM_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16")
TFL_APP_KEY = os.environ.get("TFL_APP_KEY", "")
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


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(timeout=httpx.Timeout(300.0))
    app.state.agent = AgentChatEngine(model_url=VLLM_URL, model_name=VLLM_MODEL)
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
    return {
        "gpu": {"available": True, "model": VLLM_MODEL, "status": "ready"},
        "version": "0.2.0",
    }


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


@app.post("/api/v1/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    async def _stream() -> Any:
        try:
            payload = {
                "model": VLLM_MODEL,
                "messages": [
                    {"role": "system", "content": _system_prompt()},
                    {"role": "user", "content": req.message},
                ],
                "stream": True,
                "max_tokens": 512,
                "temperature": 0.7,
            }
            async with app.state.client.stream(
                "POST", f"{VLLM_URL}/chat/completions", json=payload, timeout=120.0
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        yield f"data: {line[6:]}\n\n"
        except Exception as exc:
            logger.exception("stream failed")
            yield f"data: {{\"error\": {str(exc)!r}}}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


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
