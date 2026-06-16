"""Construct and cache voice providers from application settings."""

from __future__ import annotations

import logging

from ...core.config import get_settings
from .llm import DeepSeekLlm, LlmProvider, PlaceholderLlm
from .stt import SttProvider, UnavailableStt
from .tts import EdgeTts, FallbackTts, SapiTts, TtsProvider

logger = logging.getLogger("xz.voice.factory")

_stt: SttProvider | None = None
_llm: LlmProvider | None = None
_tts: TtsProvider | None = None


def get_llm() -> LlmProvider:
    global _llm
    if _llm is None:
        s = get_settings()
        if s.deepseek_api_key:
            try:
                logger.info("LLM provider: DeepSeek (%s)", s.llm_model)
                _llm = DeepSeekLlm(s.deepseek_api_key, s.llm_base_url, s.llm_model)
            except Exception as exc:
                logger.error("DeepSeek LLM unavailable; using PlaceholderLlm: %s", exc)
                _llm = PlaceholderLlm()
        else:
            logger.warning("deepseek_api_key is not configured; using PlaceholderLlm")
            _llm = PlaceholderLlm()
    return _llm


def get_tts() -> TtsProvider:
    global _tts
    if _tts is None:
        s = get_settings()
        logger.info("TTS provider: EdgeTTS (%s) with Windows SAPI fallback", s.tts_voice)
        _tts = FallbackTts([EdgeTts(s.tts_voice), SapiTts()])
    return _tts


def get_stt() -> SttProvider:
    global _stt
    # An UnavailableStt is NOT cached permanently: retry the real recognizer
    # on the next call (e.g. after the model finished downloading).
    if _stt is None or isinstance(_stt, UnavailableStt):
        try:
            from .stt import FunAsrStt

            _stt = FunAsrStt()
        except Exception as exc:
            logger.error("FunASR STT unavailable: %s", exc)
            _stt = UnavailableStt(str(exc))
    return _stt


def set_providers(*, stt=None, llm=None, tts=None) -> None:
    """Inject fake providers in tests."""
    global _stt, _llm, _tts
    if stt is not None:
        _stt = stt
    if llm is not None:
        _llm = llm
    if tts is not None:
        _tts = tts


def reset_providers() -> None:
    """Clear provider cache."""
    global _stt, _llm, _tts
    _stt = _llm = _tts = None
