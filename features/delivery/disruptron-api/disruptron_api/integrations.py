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


def google_maps_status() -> dict[str, object]:
    key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    return {
        "enabled": bool(key),
        "status": "configured" if key else "needs_key",
        "message": "Set GOOGLE_MAPS_API_KEY in .env for routes/places tools",
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


async def integrations_snapshot(*, force: bool = False) -> dict[str, object]:
    global _HEALTH_CACHE, _HEALTH_CACHE_AT  # noqa: PLW0603
    now = time.monotonic()
    if not force and _HEALTH_CACHE and (now - _HEALTH_CACHE_AT) < _HEALTH_TTL_S:
        return dict(_HEALTH_CACHE)

    calendar = await calendar_mcp_health()
    payload = {
        "telegram": telegram_mode(),
        "calendar": calendar,
        "google_maps": google_maps_status(),
        "elevenlabs": elevenlabs_status(),
    }
    _HEALTH_CACHE = payload
    _HEALTH_CACHE_AT = now
    return payload
