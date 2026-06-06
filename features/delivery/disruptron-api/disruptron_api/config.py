from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PACKAGE_ROOT.parents[2]
DEFAULT_SUBSCRIPTIONS = PACKAGE_ROOT.parent / "telegram-bot" / "data" / "subscriptions.json"


@dataclass(frozen=True, slots=True)
class ApiSettings:
    push_host: str
    push_port: int
    push_secret: str
    telegram_bot_token: str
    subscriptions_path: Path

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
        )
