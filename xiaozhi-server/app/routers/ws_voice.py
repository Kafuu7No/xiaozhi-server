"""WebSocket endpoint for the browser voice test page."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.voice import pipeline

logger = logging.getLogger("xz.ws.voice")
router = APIRouter()

WEB_TEST_DEVICE_ID = "web-test"


async def _process_and_reply(ws: WebSocket, pcm: bytes) -> None:
    try:
        result = await pipeline.run_turn(pcm, WEB_TEST_DEVICE_ID)
    except Exception as exc:
        logger.exception("Voice pipeline failed")
        await ws.send_json({"type": "error", "message": f"语音处理失败：{exc}"})
        await ws.send_json({"type": "reply", "text": "语音服务暂时不可用，请检查后端依赖和日志。"})
        return

    if result is None:
        await ws.send_json({"type": "stt", "text": ""})
        await ws.send_json({"type": "reply", "text": "（没有听清，请再说一次）"})
        return

    await ws.send_json({"type": "stt", "text": result.stt_text})
    await ws.send_json({"type": "reply", "text": result.reply_text})
    if result.audio_mp3:
        await ws.send_json({"type": "tts_audio"})
        await ws.send_bytes(result.audio_mp3)


@router.websocket("/ws/voice")
async def websocket_voice(ws: WebSocket) -> None:
    await ws.accept()
    logger.info("Voice test page connected")
    pcm_buffer = bytearray()
    capturing = False
    try:
        while True:
            message = await ws.receive()
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue
                msg_type = data.get("type")
                if msg_type == "start":
                    pcm_buffer.clear()
                    capturing = True
                elif msg_type == "stop":
                    capturing = False
                    await _process_and_reply(ws, bytes(pcm_buffer))
                    pcm_buffer.clear()
            elif "bytes" in message and capturing:
                pcm_buffer.extend(message["bytes"])
    except WebSocketDisconnect:
        logger.info("Voice test page disconnected")
    except Exception as exc:
        logger.exception("Voice WS error: %s", exc)
        if ws.client_state.name == "CONNECTED":
            try:
                await ws.send_json({"type": "error", "message": f"语音连接异常：{exc}"})
            except Exception:
                pass
