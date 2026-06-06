from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class TelegramDelivery:
    def __init__(self, bot_token: str) -> None:
        self._url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    async def send(self, chat_id: int, text: str) -> None:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                self._url,
                json={"chat_id": chat_id, "text": text},
            )
            if response.status_code != 200:
                logger.warning(
                    "Telegram send failed for %s: %s",
                    chat_id,
                    response.text[:200],
                )
            response.raise_for_status()
