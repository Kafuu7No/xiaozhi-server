"""Voice pipeline: STT -> LLM -> TTS, with persistence and broadcast."""

from __future__ import annotations

import logging
import asyncio
from dataclasses import dataclass

from sqlalchemy import select

from ...core.config import get_settings
from ...core.database import async_session
from ...models.database import ConversationLog
from ..broadcast import broadcast
from .factory import get_llm, get_stt, get_tts

logger = logging.getLogger("xz.voice.pipeline")

STT_PROVIDER_TIMEOUT_SECONDS = 20
STT_TRANSCRIBE_TIMEOUT_SECONDS = 45


@dataclass
class TurnResult:
    stt_text: str
    reply_text: str
    audio_mp3: bytes


async def transcribe_pcm(pcm: bytes, device_id: str) -> str:
    """Run STT only, so the device can display user text before TTS is ready."""
    try:
        stt = await asyncio.wait_for(
            asyncio.to_thread(get_stt),
            timeout=STT_PROVIDER_TIMEOUT_SECONDS,
        )
        return await asyncio.wait_for(
            stt.transcribe(pcm),
            timeout=STT_TRANSCRIBE_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        logger.error("STT timed out (device=%s)", device_id)
        raise RuntimeError("STT timed out") from exc
    except Exception as exc:
        logger.error("STT failed (device=%s): %s", device_id, exc)
        raise RuntimeError(f"STT failed: {exc}") from exc


async def _load_history(db, device_id: str, turns: int) -> list[dict]:
    result = await db.execute(
        select(ConversationLog)
        .where(ConversationLog.device_id == device_id)
        .order_by(ConversationLog.recorded_at.desc())
        .limit(turns * 2)
    )
    rows = list(reversed(result.scalars().all()))
    return [{"role": row.role, "content": row.content} for row in rows]


async def _save_turn(db, device_id: str, user_text: str, reply_text: str) -> None:
    db.add(ConversationLog(device_id=device_id, role="user", content=user_text))
    db.add(ConversationLog(device_id=device_id, role="assistant", content=reply_text))
    await db.commit()


async def complete_turn(stt_text: str, device_id: str) -> TurnResult:
    """Generate assistant text/audio after STT has already been sent to the device."""
    settings = get_settings()

    async with async_session() as db:
        history = await _load_history(db, device_id, settings.llm_history_turns)

    reply_text = await get_llm().chat(settings.llm_system_prompt, history, stt_text)
    audio_mp3 = await get_tts().synthesize(reply_text)

    async with async_session() as db:
        await _save_turn(db, device_id, stt_text, reply_text)

    for role, content in (("user", stt_text), ("assistant", reply_text)):
        await broadcast(
            "conversation",
            {"role": role, "content": content, "emotion": None},
        )

    logger.info("Voice turn done (device=%s): %r -> %r", device_id, stt_text, reply_text)
    return TurnResult(stt_text=stt_text, reply_text=reply_text, audio_mp3=audio_mp3)


async def run_turn(pcm: bytes, device_id: str) -> TurnResult | None:
    """Process one complete voice utterance. Return None if STT heard nothing."""
    settings = get_settings()

    try:
        stt = await asyncio.wait_for(
            asyncio.to_thread(get_stt),
            timeout=STT_PROVIDER_TIMEOUT_SECONDS,
        )
        stt_text = await asyncio.wait_for(
            stt.transcribe(pcm),
            timeout=STT_TRANSCRIBE_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        logger.error("STT timed out (device=%s)", device_id)
        raise RuntimeError("语音识别超时，模型可能仍在加载或下载") from exc
    except Exception as exc:
        logger.error("STT failed (device=%s): %s", device_id, exc)
        raise RuntimeError(f"语音识别失败：{exc}") from exc

    if not stt_text:
        logger.info("STT returned empty text; skipping turn (device=%s)", device_id)
        return None

    async with async_session() as db:
        history = await _load_history(db, device_id, settings.llm_history_turns)

    reply_text = await get_llm().chat(settings.llm_system_prompt, history, stt_text)
    audio_mp3 = await get_tts().synthesize(reply_text)

    async with async_session() as db:
        await _save_turn(db, device_id, stt_text, reply_text)

    for role, content in (("user", stt_text), ("assistant", reply_text)):
        await broadcast(
            "conversation",
            {"role": role, "content": content, "emotion": None},
        )

    logger.info("Voice turn done (device=%s): %r -> %r", device_id, stt_text, reply_text)
    return TurnResult(stt_text=stt_text, reply_text=reply_text, audio_mp3=audio_mp3)
