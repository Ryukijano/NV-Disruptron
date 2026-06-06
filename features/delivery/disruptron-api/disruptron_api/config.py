from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PACKAGE_ROOT.parents[2]
DEFAULT_SUBSCRIPTIONS = PACKAGE_ROOT.parent / "telegram-bot" / "data" / "subscriptions.json"


def _parse_cors_origins(raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        return ["http://localhost:5173", "http://127.0.0.1:5173"]
    return [o.strip() for o in raw.split(",") if o.strip()]


@dataclass(frozen=True, slots=True)
class ApiSettings:
    push_host: str
    push_port: int
    push_secret: str
    telegram_bot_token: str
    subscriptions_path: Path
    backend_url: str
    backend_chat_path: str
    backend_timeout_s: float
    stt_engine: str
    stt_url: str
    stt_model: str
    stt_device: str
    stt_compute_type: str
    stt_timeout_s: float
    cors_origins: tuple[str, ...]

    @classmethod
    def from_env(cls, env_path: Path | None = None) -> ApiSettings:
        if env_path and env_path.exists():
            load_dotenv(env_path)
        else:
            for candidate in (REPO_ROOT / ".env", PACKAGE_ROOT / ".env"):
                if candidate.exists():
                    load_dotenv(candidate)
                    break

        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required for outbound delivery")

        return cls(
            push_host=os.getenv("DISRUPTRON_PUSH_HOST", "127.0.0.1"),
            push_port=int(os.getenv("DISRUPTRON_PUSH_PORT", "8010")),
            push_secret=os.getenv("DISRUPTRON_PUSH_SECRET", "").strip(),
            telegram_bot_token=token,
            subscriptions_path=Path(
                os.getenv("DISRUPTRON_SUBSCRIPTIONS_PATH", str(DEFAULT_SUBSCRIPTIONS))
            ),
            backend_url=os.getenv("DISRUPTRON_BACKEND_URL", "http://127.0.0.1:18789").rstrip("/"),
            backend_chat_path=os.getenv("DISRUPTRON_BACKEND_CHAT_PATH", "/v1/chat"),
            backend_timeout_s=float(os.getenv("DISRUPTRON_BACKEND_TIMEOUT_S", "300")),
            stt_engine=os.getenv("DISRUPTRON_STT_ENGINE", "proxy").strip().lower(),
            stt_url=os.getenv(
                "DISRUPTRON_STT_URL",
                "http://127.0.0.1:8000/v1/audio/transcriptions",
            ).rstrip("/"),
            stt_model=os.getenv("DISRUPTRON_STT_MODEL", "whisper-1").strip(),
            stt_device=os.getenv("DISRUPTRON_STT_DEVICE", "cuda").strip(),
            stt_compute_type=os.getenv("DISRUPTRON_STT_COMPUTE_TYPE", "float16").strip(),
            stt_timeout_s=float(os.getenv("DISRUPTRON_STT_TIMEOUT_S", "120")),
            cors_origins=tuple(_parse_cors_origins(os.getenv("DISRUPTRON_CORS_ORIGINS"))),
        )
