from __future__ import annotations

import os
import time
from pathlib import Path

import httpx

_HEALTH_CACHE: dict[str, object] = {}
_HEALTH_CACHE_AT: float = 0.0
_HEALTH_TTL_S = 30.0


def _calendar_tokens_present() -> bool:
    token_path = Path(
        os.getenv(
            "GOOGLE_CALENDAR_MCP_TOKEN_PATH",
            str(Path.home() / ".config/google-calendar-mcp/tokens.json"),
        )
    ).expanduser()
    return token_path.is_file()


async def calendar_mcp_health() -> dict[str, object]:
    port = int(os.getenv("GOOGLE_CALENDAR_MCP_PORT", "3000"))
    url = f"http://127.0.0.1:{port}/health"
    tokens = _calendar_tokens_present()
    if not tokens:
        return {
            "enabled": os.getenv("DISRUPTRON_GOOGLE_CALENDAR", "1") != "0",
            "status": "needs_auth",
            "port": port,
            "tokens": False,
            "message": "Run: cd ~/google-calendar-mcp && npm run auth",
        }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return {
                    "enabled": True,
                    "status": "healthy",
                    "port": port,
                    "tokens": True,
                }
            return {
                "enabled": True,
                "status": "unhealthy",
                "port": port,
                "tokens": True,
                "http_status": response.status_code,
            }
    except httpx.RequestError as exc:
        return {
            "enabled": True,
            "status": "stopped",
            "port": port,
            "tokens": True,
            "message": f"Start with: ./scripts/disruptron calendar start ({exc})",
        }


def tfl_journey_status() -> dict[str, object]:
    key = os.getenv("TFL_APP_KEY", "").strip()
    return {
        "enabled": True,
        "source": "tfl_journey_planner",
        "status": "configured" if key else "anonymous",
        "message": "TfL Journey Planner (open API) — routes via tube, bus, walking, cycling. "
                   + ("App key configured." if key else "Anonymous (50 req/min)."),
    }


def elevenlabs_status() -> dict[str, object]:
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    return {
        "enabled": bool(key),
        "status": "configured" if key else "needs_key",
        "message": "Set ELEVENLABS_API_KEY in .env for web/Telegram TTS",
    }


def telegram_mode() -> dict[str, str]:
    mode = os.getenv("DISRUPTRON_TELEGRAM_MODE", "openclaw").strip().lower()
    valid = {"openclaw", "telegram-bot", "push-only"}
    if mode not in valid:
        mode = "openclaw"
    descriptions = {
        "openclaw": "OpenClaw gateway polls Telegram (interactive). disruptron-api push-only.",
        "telegram-bot": "features/delivery/telegram-bot polls and forwards to disruptron-api.",
        "push-only": "No interactive bot — disruptron-api sendMessage for alerts/daily only.",
    }
    return {
        "mode": mode,
        "recommended": "openclaw",
        "description": descriptions[mode],
        "warning": (
            "Do not run OpenClaw Telegram and telegram-bot together on the same token."
            if mode == "openclaw"
            else ""
        ),
    }


def nemotron_status() -> dict[str, object]:
    url = os.getenv("NEMOTRON_URL", "http://127.0.0.1:8008/v1")
    try:
        import httpx
        resp = httpx.get(f"{url}/models", timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get("data", [])
            model_id = models[0].get("id", "unknown") if models else "unknown"
            return {"enabled": True, "status": "healthy", "url": url, "model": model_id}
        return {"enabled": True, "status": f"http_{resp.status_code}", "url": url}
    except Exception as exc:
        return {"enabled": bool(url), "status": "unreachable", "url": url, "message": str(exc)}


def locateanything_status() -> dict[str, object]:
    from pathlib import Path
    cache = Path.home() / ".cache" / "huggingface" / "hub" / "models--nvidia--LocateAnything-3B"
    return {
        "cached": cache.exists(),
        "cache_path": str(cache),
        "status": "cached" if cache.exists() else "not_cached",
        "message": "Download with: huggingface-cli download nvidia/LocateAnything-3B" if not cache.exists() else "ready",
    }


def gpu_status() -> dict[str, object]:
    from shared.gpu import GPU_AVAILABLE, GPU_LIBS
    return {
        "gpu_available": GPU_AVAILABLE,
        "libs_loaded": list(GPU_LIBS.keys()),
        "status": "active" if GPU_AVAILABLE else "cpu_fallback",
    }


def vision_status() -> dict[str, object]:
    from pathlib import Path
    hazard_geojson = (
        Path(__file__).resolve().parents[4] / "data" / "geo" / "hazards.geojson"
    )
    return {
        "hazard_geojson_exists": hazard_geojson.exists(),
        "hazard_geojson_path": str(hazard_geojson),
    }


async def integrations_snapshot(*, force: bool = False) -> dict[str, object]:
    global _HEALTH_CACHE, _HEALTH_CACHE_AT  # noqa: PLW0603
    now = time.monotonic()
    if not force and _HEALTH_CACHE and (now - _HEALTH_CACHE_AT) < _HEALTH_TTL_S:
        return dict(_HEALTH_CACHE)

    calendar = await calendar_mcp_health()
    payload = {
        "telegram": telegram_mode(),
        "calendar": calendar,
        "tfl_journey": tfl_journey_status(),
        "elevenlabs": elevenlabs_status(),
        "nemotron": nemotron_status(),
        "locateanything": locateanything_status(),
        "gpu": gpu_status(),
        "vision": vision_status(),
    }
    _HEALTH_CACHE = payload
    _HEALTH_CACHE_AT = now
    return payload
