"""WebSocket endpoint for XiaoZhi device communication."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from ..core.config import get_settings
from ..core.database import async_session
from ..models.protocol import DeviceSession, DeviceState
from ..services import (
    meow_service,
    peer_config_service,
    sensor_pipeline,
    sensor_service,
    settings_service,
    water_service,
)
from ..services.broadcast import broadcast
from ..services.voice.official_proxy import OfficialVoiceProxy
from ..services.session_manager import session_manager
from . import meow as meow_router

logger = logging.getLogger("xz.ws")
router = APIRouter()

AUTO_STOP_SILENCE_SECONDS = 0.9
AUTO_STOP_MAX_SECONDS = 12.0
AUTO_STOP_MIN_VOICE_FRAMES = 3
AUTO_STOP_VOICE_RMS = 350.0
TTS_START_SETTLE_SECONDS = 0.05
TTS_STOP_MARGIN_SECONDS = 0.35
TTS_FRAME_MIN_INTERVAL_SECONDS = 0.01
TTS_FRAME_MAX_INTERVAL_SECONDS = 0.08


def _parse_headers(ws: WebSocket) -> tuple[str, str]:
    headers = dict(ws.headers)
    return headers.get("device-id", ""), headers.get("client-id", "")


def _use_official_voice() -> bool:
    return get_settings().voice_upstream.lower() == "official"


def _get_voice_proxy(session: DeviceSession, ws: WebSocket) -> OfficialVoiceProxy:
    proxy = session.voice_proxy
    if not isinstance(proxy, OfficialVoiceProxy):
        proxy = OfficialVoiceProxy(session, ws)
        session.voice_proxy = proxy
    return proxy


async def _close_voice_proxy(session: DeviceSession) -> None:
    proxy = session.voice_proxy
    session.voice_proxy = None
    if isinstance(proxy, OfficialVoiceProxy):
        await proxy.close()


def _cancel_auto_stop(session: DeviceSession) -> None:
    task = session.auto_stop_task
    if task and not task.done() and task is not asyncio.current_task():
        task.cancel()
    session.auto_stop_task = None


def _reset_listen_stats(session: DeviceSession) -> None:
    session.listen_started_at = time.monotonic()
    session.last_voice_at = 0.0
    session.voice_frame_count = 0
    session.voice_turn_running = False


def _frame_rms(data: bytes) -> float:
    from ..services.voice import audio_codec

    pcm = audio_codec.decode_opus_frames([data])
    if len(pcm) < 2:
        return 0.0
    samples = memoryview(pcm).cast("h")
    if not samples:
        return 0.0
    total = sum(int(sample) * int(sample) for sample in samples)
    return math.sqrt(total / len(samples))


def _update_voice_stats(session: DeviceSession, data: bytes) -> None:
    try:
        rms = _frame_rms(data)
    except Exception as exc:
        logger.debug("Auto-stop RMS check failed: %s", exc)
        return
    if rms >= AUTO_STOP_VOICE_RMS:
        session.last_voice_at = time.monotonic()
        session.voice_frame_count += 1


async def _send_device_json(session: DeviceSession, ws: WebSocket, payload: dict) -> None:
    if ws.client_state == WebSocketState.CONNECTED:
        async with session.device_send_lock:
            await ws.send_text(
                json.dumps({"session_id": session.session_id, **payload}, ensure_ascii=False)
            )


async def _send_tts_stop(session: DeviceSession, ws: WebSocket) -> None:
    await _send_device_json(session, ws, {"type": "tts", "state": "stop"})


def _tts_frame_interval_seconds(pcm: bytes, sample_rate: int, frame_count: int) -> float:
    if not pcm:
        return 0.0
    duration = len(pcm) / float(sample_rate * 2)
    return min(
        max(duration / max(frame_count, 1), TTS_FRAME_MIN_INTERVAL_SECONDS),
        TTS_FRAME_MAX_INTERVAL_SECONDS,
    )


async def _auto_stop_monitor(session_id: str) -> None:
    settings = get_settings()
    interval = max(settings.audio_frame_duration / 1000, 0.1)
    try:
        while True:
            await asyncio.sleep(interval)
            pair = session_manager.get_session(session_id)
            if not pair:
                return

            session, _ = pair
            if session.state != DeviceState.LISTENING:
                return
            if session.listen_mode != "auto_stop" or session.voice_turn_running:
                return
            if not session.audio_buffer:
                continue

            now = time.monotonic()
            heard_voice = session.voice_frame_count >= AUTO_STOP_MIN_VOICE_FRAMES
            silence_elapsed = (
                heard_voice
                and session.last_voice_at > 0
                and now - session.last_voice_at >= AUTO_STOP_SILENCE_SECONDS
            )
            max_elapsed = now - session.listen_started_at >= AUTO_STOP_MAX_SECONDS
            if silence_elapsed or max_elapsed:
                reason = "silence" if silence_elapsed else "max_duration"
                await _finish_listen(session_id, reason=reason)
                return
    except asyncio.CancelledError:
        return


def _start_auto_stop(session_id: str, session: DeviceSession) -> None:
    if session.listen_mode != "auto_stop":
        return
    _cancel_auto_stop(session)
    session.auto_stop_task = asyncio.create_task(_auto_stop_monitor(session_id))


async def _broadcast_device_status(session: DeviceSession, *, connected: bool) -> None:
    await broadcast(
        "device_status",
        {
            "device_id": session.device_id,
            "state": session.state.value if connected else "disconnected",
            "iot_states": session.iot_states,
            "connected": connected,
        },
    )


def _check_auth(ws: WebSocket) -> bool:
    settings = get_settings()
    auth_header = ws.headers.get("authorization", "")

    scheme, _, value = auth_header.partition(" ")
    token = value.strip() if scheme.lower() == "bearer" else auth_header.strip()
    if not token:
        token = ws.query_params.get("token", "")
    return token == settings.device_token


async def _handle_hello(ws: WebSocket, data: dict) -> str | None:
    settings = get_settings()
    device_id, client_id = _parse_headers(ws)

    logger.info(
        "Hello from device: version=%s, device_id=%s, features=%s",
        data.get("version", "?"),
        device_id,
        data.get("features", {}),
    )

    session = session_manager.create_session(ws, device_id, client_id)
    session.state = DeviceState.IDLE

    await ws.send_json(
        {
            "type": "hello",
            "transport": "websocket",
            "session_id": session.session_id,
            "audio_params": {
                "format": "opus",
                "sample_rate": settings.audio_tts_sample_rate,
                "channels": 1,
                "frame_duration": settings.audio_frame_duration,
            },
        }
    )
    await _broadcast_device_status(session, connected=True)
    logger.info("Hello response sent, session_id=%s", session.session_id)
    try:
        async with async_session() as db:
            await peer_config_service.push_peer_config(db)
    except Exception:
        logger.exception("peer_config push on hello failed")

    if _use_official_voice():
        async def warm_official_voice() -> None:
            try:
                await _get_voice_proxy(session, ws).connect()
            except Exception as exc:
                logger.error("Official voice warmup failed: %s", exc)

        asyncio.create_task(warm_official_voice())
    return session.session_id


async def _handle_listen(data: dict, session_id: str) -> None:
    pair = session_manager.get_session(session_id)
    if not pair:
        logger.warning("Listen message for unknown session: %s", data.get("session_id"))
        return

    session, ws = pair
    state = data.get("state", "")
    mode = data.get("mode", "auto_stop")

    if state == "start":
        _cancel_auto_stop(session)
        session.state = DeviceState.LISTENING
        session.listen_mode = mode
        session.audio_buffer = []
        _reset_listen_stats(session)
        if _use_official_voice():
            try:
                await _get_voice_proxy(session, ws).send_json(
                    {"type": "listen", "state": "start", "mode": mode}
                )
            except Exception as exc:
                session.state = DeviceState.IDLE
                logger.error("Official listen start failed (session=%s): %s", session_id, exc)
                await _send_tts_stop(session, ws)
            else:
                logger.info("Device listening via official voice (mode=%s, session=%s)", mode, session_id)
            await _broadcast_device_status(session, connected=True)
            return

        logger.info("Device listening locally (mode=%s, session=%s)", mode, session_id)
        _start_auto_stop(session_id, session)
    elif state == "stop":
        if _use_official_voice():
            try:
                await _get_voice_proxy(session, ws).send_json({"type": "listen", "state": "stop"})
            except Exception as exc:
                logger.error("Official listen stop failed (session=%s): %s", session_id, exc)
            session.state = DeviceState.IDLE
            session.audio_buffer = []
            await _broadcast_device_status(session, connected=True)
            return

        await _finish_listen(session_id, reason="client_stop")
        return
    else:
        logger.warning("Unknown listen state: %s", state)
        return

    await _broadcast_device_status(session, connected=True)


async def _handle_iot(data: dict, session_id: str) -> None:
    pair = session_manager.get_session(session_id)
    if not pair:
        return

    session, _ = pair

    if "descriptors" in data:
        session.iot_descriptors = data["descriptors"]
        logger.info(
            "IoT descriptors received: %d devices (session=%s)",
            len(session.iot_descriptors),
            session_id,
        )

    if "states" in data:
        session.iot_states = data["states"]
        logger.info(
            "IoT states received: %d devices (session=%s)",
            len(session.iot_states),
            session_id,
        )
        await broadcast("iot_state_changed", {"states": session.iot_states})
        await _broadcast_device_status(session, connected=True)


async def _forward_official_json(data: dict, session_id: str) -> None:
    if not _use_official_voice():
        return
    pair = session_manager.get_session(session_id)
    if not pair:
        return

    session, ws = pair
    try:
        await _get_voice_proxy(session, ws).send_json(data)
    except Exception as exc:
        logger.error(
            "Official JSON forward failed: type=%s session=%s error=%s",
            data.get("type", ""),
            session_id,
            exc,
        )


async def _handle_env(ws: WebSocket, data: dict, session_id: str) -> None:
    del ws
    pair = session_manager.get_session(session_id)
    if not pair:
        return

    session, _ = pair
    parsed = sensor_pipeline.parse_sensor_payload(data)
    if not parsed:
        logger.warning("Env message missing temperature/humidity (session=%s)", session_id)
        return

    temp_c = parsed["temperature"]
    humi_rh = parsed["humidity"]
    device_ts = data.get("ts")
    sensor_ok = data.get("sensor_ok")
    sensor_error = data.get("sensor_error")
    source = "env_fallback" if sensor_ok is False else "env"

    if not isinstance(temp_c, (int, float)) or not isinstance(humi_rh, (int, float)):
        logger.warning("Env message missing temp_c/humi_rh (session=%s)", session_id)
        return

    async with async_session() as db:
        await sensor_service.save_record(
            db,
            device_id=session.device_id,
            temp_c=float(temp_c),
            humi_rh=float(humi_rh),
            ts=int(device_ts) if isinstance(device_ts, (int, float)) else None,
            source=source,
            sensor_ok=sensor_ok if isinstance(sensor_ok, bool) else None,
            sensor_error=str(sensor_error)[:80] if sensor_error else None,
        )


async def _handle_meow(data: dict, session_id: str) -> None:
    pair = session_manager.get_session(session_id)
    if not pair:
        return

    session, _ = pair

    async with async_session() as db:
        threshold = await settings_service.get_meow_threshold(db)
        min_confidence = await settings_service.get_meow_min_confidence(db)
        parsed = meow_service.parse_meow_payload(data, threshold)
        if not parsed:
            logger.warning("Meow message missing score (session=%s)", session_id)
            return

        await meow_service.save_event(
            db,
            device_id=session.device_id,
            score=parsed["score"],
            is_cat=parsed["is_cat"],
            min_confidence=min_confidence,
            ts=parsed.get("ts"),
            source="meow",
        )


async def _handle_meow_water(data: dict, session_id: str) -> None:
    """board1 fired the pump directly to board2 because of '3 meows in 10s'.

    The cloud is not in that UDP path, so the device notifies us here and we
    log it into the water records as a '猫叫触发' (cat-meow triggered) dispense.
    """
    pair = session_manager.get_session(session_id)
    if not pair:
        return

    session, _ = pair

    raw = data.get("duration")
    try:
        duration = float(raw)
    except (TypeError, ValueError):
        duration = 5.0
    if duration <= 0:
        duration = 5.0

    async with async_session() as db:
        await water_service.create_pump_record(
            db,
            device_id=session.device_id,
            duration_seconds=duration,
            trigger_type="猫叫触发",
        )
    logger.info("Meow-triggered water recorded (session=%s, %.0fs)", session_id, duration)


async def _handle_meow_status(data: dict, session_id: str) -> None:
    pair = session_manager.get_session(session_id)
    if not pair:
        return

    session, _ = pair
    enabled = data.get("enabled")
    result = data.get("result")
    message = data.get("message")

    await meow_router.update_meow_status(
        enabled=bool(enabled),
        result=int(result) if isinstance(result, (int, float)) and not isinstance(result, bool) else None,
        message=str(message)[:80] if message else "",
        device_id=session.device_id,
    )


async def _handle_audio_binary(data: bytes, session_id: str) -> None:
    pair = session_manager.get_session(session_id)
    if not pair:
        return
    session, ws = pair
    if session.state != DeviceState.LISTENING:
        return
    if _use_official_voice():
        try:
            await _get_voice_proxy(session, ws).send_audio(data)
        except Exception as exc:
            logger.error("Official audio forward failed (session=%s): %s", session_id, exc)
            session.state = DeviceState.IDLE
            await _broadcast_device_status(session, connected=True)
            await _send_tts_stop(session, ws)
        else:
            session.voice_frame_count += 1
            if session.voice_frame_count % 50 == 0:
                logger.debug(
                    "Audio frame forwarded to official: %d bytes, total %d frames (session=%s)",
                    len(data),
                    session.voice_frame_count,
                    session_id,
                )
        return

    session.audio_buffer.append(data)
    if session.listen_mode == "auto_stop":
        _update_voice_stats(session, data)
    if len(session.audio_buffer) % 50 == 0:
        logger.debug(
            "Audio frame buffered: %d bytes, total %d frames, voice=%d (session=%s)",
            len(data),
            len(session.audio_buffer),
            session.voice_frame_count,
            session_id,
        )


async def _finish_listen(session_id: str, *, reason: str) -> None:
    pair = session_manager.get_session(session_id)
    if not pair:
        return

    session, ws = pair
    if session.voice_turn_running:
        return

    _cancel_auto_stop(session)
    frames = session.audio_buffer
    session.audio_buffer = []
    session.state = DeviceState.IDLE
    session.voice_turn_running = True
    logger.info(
        "Device stopped listening by %s, %d audio frames (voice=%d, session=%s)",
        reason,
        len(frames),
        session.voice_frame_count,
        session_id,
    )
    await _broadcast_device_status(session, connected=True)

    try:
        if frames:
            await _run_voice_turn(session, ws, frames)
        else:
            await _send_tts_stop(session, ws)
    finally:
        session.voice_turn_running = False


async def _run_voice_turn(session: DeviceSession, ws: WebSocket, frames: list[bytes]) -> None:
    """Decode device audio, run the voice pipeline, and send Opus frames back."""
    from ..services.voice import audio_codec, pipeline

    try:
        pcm = audio_codec.decode_opus_frames(frames)
        stt_text = await pipeline.transcribe_pcm(pcm, session.device_id)
        await _send_device_json(session, ws, {"type": "stt", "text": stt_text})
        if not stt_text:
            logger.info("STT returned empty text; skipping turn (session=%s)", session.session_id)
            await _send_tts_stop(session, ws)
            return

        result = await pipeline.complete_turn(stt_text, session.device_id)
        await _send_device_json(session, ws, {"type": "tts", "state": "start"})
        await _send_device_json(
            session,
            ws,
            {"type": "tts", "state": "sentence_start", "text": result.reply_text},
        )
        await asyncio.sleep(TTS_START_SETTLE_SECONDS)

        frame_count = 0
        frame_interval = 0.0
        if result.audio_mp3:
            sample_rate = get_settings().audio_tts_sample_rate
            pcm_out = audio_codec.decode_mp3_to_pcm(
                result.audio_mp3,
                sample_rate=sample_rate,
            )
            opus_frames = audio_codec.encode_pcm_to_opus(pcm_out)
            frame_count = len(opus_frames)
            frame_interval = _tts_frame_interval_seconds(pcm_out, sample_rate, frame_count)
            logger.info(
                "TTS downlink streaming %d opus frames, frame_interval=%.3fs (session=%s)",
                frame_count,
                frame_interval,
                session.session_id,
            )
            for frame in opus_frames:
                async with session.device_send_lock:
                    await ws.send_bytes(frame)
                if frame_interval:
                    await asyncio.sleep(frame_interval)

        await asyncio.sleep(TTS_STOP_MARGIN_SECONDS)
        await _send_device_json(
            session,
            ws,
            {"type": "tts", "state": "sentence_end", "text": result.reply_text},
        )
        await asyncio.sleep(TTS_START_SETTLE_SECONDS)
        await _send_tts_stop(session, ws)
        logger.info(
            "TTS downlink complete, frames=%d (session=%s)",
            frame_count,
            session.session_id,
        )
    except Exception as exc:
        logger.error("Voice turn failed (session=%s): %s", session.session_id, exc)
        try:
            await _send_tts_stop(session, ws)
        except Exception:
            logger.exception("Failed to send TTS stop after voice failure")


@router.websocket("/xiaozhi/v1/")
async def websocket_device(ws: WebSocket):
    if not _check_auth(ws):
        logger.warning("Auth failed from %s", ws.client.host if ws.client else "unknown")
        await ws.close(code=4001, reason="Unauthorized")
        return

    await ws.accept()
    logger.info("WebSocket accepted from %s", ws.client.host if ws.client else "unknown")

    session_id: str | None = None

    try:
        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect

            if "text" in message:
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON received")
                    continue

                msg_type = data.get("type", "")

                if msg_type == "hello":
                    session_id = await _handle_hello(ws, data)
                elif msg_type == "listen":
                    await _handle_listen(data, session_id or "")
                elif msg_type == "iot":
                    await _handle_iot(data, session_id or "")
                    await _forward_official_json(data, session_id or "")
                elif msg_type == "mcp":
                    await _forward_official_json(data, session_id or "")
                elif msg_type == "env":
                    await _handle_env(ws, data, session_id or "")
                elif msg_type == "sensor":
                    await _handle_env(ws, data, session_id or "")
                elif msg_type == "meow":
                    await _handle_meow(data, session_id or "")
                elif msg_type == "meow_water":
                    await _handle_meow_water(data, session_id or "")
                elif msg_type == "meow_status":
                    await _handle_meow_status(data, session_id or "")
                else:
                    logger.warning("Unknown message type: %s", msg_type)
            elif "bytes" in message and session_id:
                await _handle_audio_binary(message["bytes"], session_id)
    except WebSocketDisconnect:
        logger.info("Device disconnected (session=%s)", session_id)
    except Exception as exc:
        logger.error("WebSocket error: %s (session=%s)", exc, session_id)
    finally:
        if session_id:
            pair = session_manager.get_session(session_id)
            if pair:
                session, stored_ws = pair
                _cancel_auto_stop(session)
                await _close_voice_proxy(session)
                if stored_ws.client_state == WebSocketState.CONNECTED:
                    try:
                        async with session.device_send_lock:
                            await stored_ws.send_json({"type": "goodbye"})
                    except Exception:
                        pass
                session_manager.remove_session(session_id)
                await meow_router.update_meow_status(
                    enabled=False,
                    message="device_disconnected",
                    device_id=session.device_id,
                )
                await _broadcast_device_status(session, connected=False)
