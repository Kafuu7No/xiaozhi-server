from sqlalchemy import select

from app.core.database import async_session
from app.models.database import ConversationLog
from app.services.voice import factory, pipeline


class FakeStt:
    def __init__(self, text):
        self._text = text

    async def transcribe(self, pcm):
        return self._text


class FakeLlm:
    async def chat(self, system_prompt, history, user_text):
        return f"reply-to:{user_text}"


class FakeTts:
    async def synthesize(self, text):
        return b"FAKE_MP3"


async def test_run_turn_returns_result_and_writes_db(db_ready):
    factory.set_providers(stt=FakeStt("你好猫窝"), llm=FakeLlm(), tts=FakeTts())
    result = await pipeline.run_turn(b"\x00\x00" * 1600, "web-test")

    assert result is not None
    assert result.stt_text == "你好猫窝"
    assert result.reply_text == "reply-to:你好猫窝"
    assert result.audio_mp3 == b"FAKE_MP3"

    async with async_session() as db:
        rows = (await db.execute(select(ConversationLog))).scalars().all()
    assert {row.role for row in rows} == {"user", "assistant"}
    factory.reset_providers()


async def test_run_turn_skips_when_stt_empty(db_ready):
    factory.set_providers(stt=FakeStt(""), llm=FakeLlm(), tts=FakeTts())
    result = await pipeline.run_turn(b"\x00\x00" * 100, "web-test")

    assert result is None
    async with async_session() as db:
        rows = (await db.execute(select(ConversationLog))).scalars().all()
    assert rows == []
    factory.reset_providers()
