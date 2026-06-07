"""ElevenLabs TTS for web playback."""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

ELEVENLABS_UNAVAILABLE = "ElevenLabs TTS not configured (set ELEVENLABS_API_KEY in .env)"


class ElevenLabsTTS:
    def __init__(
        self,
        *,
        api_key: str,
        voice_id: str = "pMsXgVXv3BLzUgSXRplE",
        model_id: str = "eleven_multilingual_v2",
        timeout_s: float = 60.0,
    ) -> None:
        self._api_key = api_key.strip()
        self._voice_id = voice_id
        self._model_id = model_id
        self._timeout = httpx.Timeout(timeout_s)

    @classmethod
    def from_env(cls) -> ElevenLabsTTS | None:
        key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        if not key:
            return None
        return cls(
            api_key=key,
            voice_id=os.getenv("ELEVENLABS_VOICE_ID", "pMsXgVXv3BLzUgSXRplE"),
            model_id=os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
        )

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def synthesize(self, text: str) -> bytes:
        if not self._api_key:
            raise RuntimeError(ELEVENLABS_UNAVAILABLE)
        trimmed = text.strip()[:480]
        if not trimmed:
            raise ValueError("Empty text for TTS")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self._voice_id}"
        payload = {
            "text": trimmed,
            "model_id": self._model_id,
            "voice_settings": {"stability": 0.55, "similarity_boost": 0.75},
        }
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                logger.warning("ElevenLabs TTS HTTP %s", response.status_code)
                raise RuntimeError("ElevenLabs synthesis failed")
            return response.content
