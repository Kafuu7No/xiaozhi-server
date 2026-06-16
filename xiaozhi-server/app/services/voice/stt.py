"""STT providers: abstract base and FunASR."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger("xz.voice.stt")

# Pre-downloaded model (from hf-mirror) so STT never needs network at runtime.
LOCAL_MODEL_DIR = Path(__file__).resolve().parents[3] / "models" / "paraformer-zh"


def local_model_available() -> bool:
    return (LOCAL_MODEL_DIR / "config.yaml").exists() and (LOCAL_MODEL_DIR / "model.pt").exists()


class SttProvider(ABC):
    """Speech-to-text interface."""

    @abstractmethod
    async def transcribe(self, pcm: bytes) -> str:
        """Transcribe 16kHz mono 16-bit little-endian PCM bytes."""


class UnavailableStt(SttProvider):
    """Fallback STT used when the real recognizer is missing or still unavailable."""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    async def transcribe(self, pcm: bytes) -> str:
        logger.warning("STT unavailable: %s", self.reason)
        return ""


class FunAsrStt(SttProvider):
    """Local/offline Chinese STT via FunASR."""

    def __init__(self, model_name: str = "paraformer-zh") -> None:
        from funasr import AutoModel

        if local_model_available():
            model_name = str(LOCAL_MODEL_DIR)
        logger.info("Loading FunASR model '%s' (first run may download it)...", model_name)
        self._model = AutoModel(model=model_name, disable_update=True)
        logger.info("FunASR model loaded")

    async def transcribe(self, pcm: bytes) -> str:
        if not pcm:
            return ""
        return await asyncio.to_thread(self._transcribe_sync, pcm)

    def _transcribe_sync(self, pcm: bytes) -> str:
        import numpy as np

        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        try:
            res = self._model.generate(input=audio)
        except Exception as exc:
            logger.error("STT failed: %s", exc)
            return ""
        if not res:
            return ""
        return str(res[0].get("text", "")).strip()
