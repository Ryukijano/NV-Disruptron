from __future__ import annotations

import logging

from disruptron_api.backend.transcribe import TranscribeEngine, TranscribeProxy, WhisperLocalEngine
from disruptron_api.config import ApiSettings

logger = logging.getLogger(__name__)


def build_transcribe_engine(settings: ApiSettings) -> TranscribeEngine | None:
    engine = settings.stt_engine
    if engine in {"", "off", "disabled", "none"}:
        return None
    if engine == "whisper":
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            logger.error("DISRUPTRON_STT_ENGINE=whisper but faster-whisper is not installed")
            return None
        return WhisperLocalEngine(
            settings.stt_model,
            settings.stt_device,
            settings.stt_compute_type,
        )
    if engine == "proxy":
        return TranscribeProxy(settings.stt_url, settings.stt_model, settings.stt_timeout_s)
    logger.warning("Unknown DISRUPTRON_STT_ENGINE=%s", engine)
    return None
