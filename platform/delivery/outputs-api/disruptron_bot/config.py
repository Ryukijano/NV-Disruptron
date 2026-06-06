from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PACKAGE_ROOT.parents[2]
DEFAULT_SUBSCRIPTIONS = PACKAGE_ROOT / "data" / "subscriptions.json"


def _parse_allowlist(raw: str | None) -> frozenset[int] | None:
    if not raw or not raw.strip():
        return None
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        token = part.strip().removeprefix("tg:").removeprefix("telegram:")
        if not token or token == "*":
            continue
        ids.add(int(token))
    return frozenset(ids) if ids else None


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    push_host: str
    push_port: int
    push_secret: str
    backend_url: str
    backend_chat_path: str
    backend_timeout_s: float
    subscriptions_path: Path
    allow_from: frozenset[int] | None

    @classmethod
    def from_env(cls, env_path: Path | None = None) -> Settings:
        if env_path and env_path.exists():
            load_dotenv(env_path)
        else:
            for candidate in (REPO_ROOT / ".env", PACKAGE_ROOT / ".env"):
                if candidate.exists():
                    load_dotenv(candidate)
                    break

        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")

        return cls(
            bot_token=token,
            push_host=os.getenv("DISRUPTRON_PUSH_HOST", "127.0.0.1"),
            push_port=int(os.getenv("DISRUPTRON_PUSH_PORT", "8010")),
            push_secret=os.getenv("DISRUPTRON_PUSH_SECRET", "").strip(),
            backend_url=os.getenv("DISRUPTRON_BACKEND_URL", "http://127.0.0.1:18789").rstrip("/"),
            backend_chat_path=os.getenv("DISRUPTRON_BACKEND_CHAT_PATH", "/v1/chat"),
            backend_timeout_s=float(os.getenv("DISRUPTRON_BACKEND_TIMEOUT_S", "300")),
            subscriptions_path=Path(
                os.getenv("DISRUPTRON_SUBSCRIPTIONS_PATH", str(DEFAULT_SUBSCRIPTIONS))
            ),
            allow_from=_parse_allowlist(os.getenv("TELEGRAM_ALLOW_FROM")),
        )
