"""FallbackTts: provider ordering and per-request fallback."""

import pytest

from app.services.voice.tts import FallbackTts, TtsProvider


class FakeTts(TtsProvider):
    def __init__(self, audio: bytes) -> None:
        self.audio = audio
        self.calls = 0

    async def synthesize(self, text: str) -> bytes:
        self.calls += 1
        return self.audio


@pytest.mark.asyncio
async def test_falls_back_when_first_provider_returns_empty():
    bad, good = FakeTts(b""), FakeTts(b"WAV")
    tts = FallbackTts([bad, good])
    assert await tts.synthesize("hi") == b"WAV"
    assert bad.calls == 1 and good.calls == 1


@pytest.mark.asyncio
async def test_retries_primary_provider_each_call():
    bad, good = FakeTts(b""), FakeTts(b"WAV")
    tts = FallbackTts([bad, good])
    await tts.synthesize("hi")
    await tts.synthesize("again")
    assert bad.calls == 2 and good.calls == 2


@pytest.mark.asyncio
async def test_all_fail_returns_empty():
    tts = FallbackTts([FakeTts(b""), FakeTts(b"")])
    assert await tts.synthesize("hi") == b""
