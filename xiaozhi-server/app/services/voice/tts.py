"""TTS providers: EdgeTTS (online), Windows SAPI (offline fallback)."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import tempfile
from abc import ABC, abstractmethod

logger = logging.getLogger("xz.voice.tts")

EDGE_TTS_TIMEOUT_SECONDS = 20.0


class TtsProvider(ABC):
    """Speech synthesis interface."""

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Synthesize text into MP3 bytes; return b'' on failure or empty text."""


class EdgeTts(TtsProvider):
    """Microsoft EdgeTTS provider. It needs no API key and returns MP3 bytes."""

    def __init__(self, voice: str) -> None:
        self._voice = voice

    async def synthesize(self, text: str) -> bytes:
        if not text.strip():
            return b""
        try:
            return await asyncio.wait_for(self._stream(text), EDGE_TTS_TIMEOUT_SECONDS)
        except Exception as exc:
            logger.error("EdgeTTS failed: %s: %s", type(exc).__name__, exc)
            return b""

    async def _stream(self, text: str) -> bytes:
        import edge_tts

        communicate = edge_tts.Communicate(text, self._voice)
        audio = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
        return bytes(audio)


class SapiTts(TtsProvider):
    """Offline TTS via Windows SAPI (System.Speech), e.g. 'Microsoft Huihui Desktop'.

    Needs no network. Returns WAV bytes; the codec layer sniffs the container,
    so WAV works anywhere MP3 does.
    """

    def __init__(self, voice_hint: str = "Huihui") -> None:
        self._voice_hint = voice_hint

    async def synthesize(self, text: str) -> bytes:
        if not text.strip():
            return b""
        return await asyncio.to_thread(self._synthesize_sync, text)

    def _synthesize_sync(self, text: str) -> bytes:
        tmp_dir = tempfile.mkdtemp(prefix="xz_sapi_")
        txt_path = os.path.join(tmp_dir, "text.txt")
        wav_path = os.path.join(tmp_dir, "out.wav")
        try:
            with open(txt_path, "w", encoding="utf-8") as fh:
                fh.write(text)
            # Text goes through a UTF-8 file to dodge console codepage issues.
            script = (
                "Add-Type -AssemblyName System.Speech; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$v = $s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Name -like '*{self._voice_hint}*' }} | Select-Object -First 1; "
                "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }; "
                f"$s.SetOutputToWaveFile('{wav_path}'); "
                f"$text = [IO.File]::ReadAllText('{txt_path}', [Text.Encoding]::UTF8); "
                "$s.Speak($text); $s.Dispose()"
            )
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                timeout=30,
            )
            if proc.returncode != 0:
                logger.error("SAPI TTS failed: %s", proc.stderr.decode(errors="replace")[:200])
                return b""
            with open(wav_path, "rb") as fh:
                return fh.read()
        except Exception as exc:
            logger.error("SAPI TTS failed: %s", exc)
            return b""
        finally:
            for path in (txt_path, wav_path):
                try:
                    os.unlink(path)
                except OSError:
                    pass
            try:
                os.rmdir(tmp_dir)
            except OSError:
                pass


class FallbackTts(TtsProvider):
    """Try providers in order; keep SAPI as a per-request fallback only."""

    def __init__(self, providers: list[TtsProvider]) -> None:
        if not providers:
            raise ValueError("FallbackTts needs at least one provider")
        self._providers = list(providers)

    async def synthesize(self, text: str) -> bytes:
        for idx, provider in enumerate(self._providers):
            audio = await provider.synthesize(text)
            if audio:
                if idx != 0:
                    logger.info("TTS fell back to %s", type(provider).__name__)
                return audio
        logger.error("All TTS providers failed for text: %r", text[:50])
        return b""
