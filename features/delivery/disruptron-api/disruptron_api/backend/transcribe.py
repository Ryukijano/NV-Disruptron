from __future__ import annotations

import asyncio
import logging
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)

STT_UNAVAILABLE = "Speech transcription is temporarily unavailable."


class TranscribeEngine(Protocol):
    async def transcribe(self, audio: bytes, filename: str, content_type: str) -> str: ...


class TranscribeProxy:
    def __init__(self, url: str, model: str, timeout_s: float) -> None:
        self._url = url.rstrip("/")
        self._model = model
        self._timeout = httpx.Timeout(timeout_s)

    async def transcribe(self, audio: bytes, filename: str, content_type: str) -> str:
        files = {"file": (filename, audio, content_type or "audio/webm")}
        data = {"model": self._model}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self._url, files=files, data=data)
                response.raise_for_status()
                payload = response.json()
                text = payload.get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
                return STT_UNAVAILABLE
        except httpx.HTTPStatusError as exc:
            logger.warning("stt proxy HTTP %s", exc.response.status_code)
            return STT_UNAVAILABLE
        except httpx.RequestError as exc:
            logger.warning("stt proxy unreachable at %s: %s", self._url, exc)
            return STT_UNAVAILABLE


class WhisperLocalEngine:
    def __init__(self, model_name: str, device: str, compute_type: str) -> None:
        self._model_name = model_name
        self._device = device
        self._compute_type = compute_type
        self._model = None

    def _load(self):
        if self._model is not None:
            return self._model
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            self._model_name,
            device=self._device,
            compute_type=self._compute_type,
        )
        return self._model

    def _transcribe_sync(self, audio: bytes) -> str:
        import tempfile
        from pathlib import Path

        model = self._load()
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(audio)
            path = Path(tmp.name)
        try:
            segments, _ = model.transcribe(str(path), language="en", vad_filter=True)
            text = " ".join(segment.text.strip() for segment in segments).strip()
            return text or STT_UNAVAILABLE
        finally:
            path.unlink(missing_ok=True)

    async def transcribe(self, audio: bytes, filename: str, content_type: str) -> str:
        del filename, content_type
        return await asyncio.to_thread(self._transcribe_sync, audio)
