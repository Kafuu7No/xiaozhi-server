"""Proxy device voice traffic to the official XiaoZhi websocket."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import aiohttp
from starlette.websockets import WebSocketState

from ...core.config import get_settings
from ...models.protocol import DeviceSession, DeviceState

logger = logging.getLogger("xz.voice.official")


class OfficialVoiceProxy:
    """One upstream official websocket per local device session."""

    def __init__(self, session: DeviceSession, device_ws) -> None:
        self.session = session
        self.device_ws = device_ws
        self._client: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._recv_task: asyncio.Task | None = None
        self._connect_lock = asyncio.Lock()
        self._send_lock = asyncio.Lock()
        self._official_session_id = ""
        self._tts_started = False
        self._downlink_binary_frames = 0
        self._closed = False
        # Playback-time bookkeeping: frames forward immediately (the board
        # buffers up to 256), but control messages (sentence_end / stop) are
        # held back until the board has actually PLAYED the queued audio --
        # the firmware's stop handler flushes the playback queue, so an early
        # stop chops off the tail of the reply.
        self._playback_until = 0.0
        self._turn_last_frame_at = 0.0
        self._turn_gap_count = 0
        self._turn_gap_max = 0.0

    async def connect(self) -> None:
        if self._ws and not self._ws.closed:
            return

        async with self._connect_lock:
            if self._closed:
                raise RuntimeError("official voice proxy is closed")
            if self._ws and not self._ws.closed:
                return

            # The network path to tenclass drops TLS handshakes intermittently;
            # a couple of quick retries rides over most of it.
            last_exc: Exception | None = None
            for attempt in range(3):
                try:
                    await self._connect_once()
                    return
                except Exception as exc:
                    last_exc = exc
                    await self._teardown_ws()
                    if attempt < 2:
                        await asyncio.sleep(0.5 * (attempt + 1))
            assert last_exc is not None
            raise last_exc

    async def _connect_once(self) -> None:
        settings = get_settings()
        headers = {
            "Protocol-Version": "1",
            "Device-Id": self.session.device_id,
            "Client-Id": self.session.client_id,
        }
        if settings.official_voice_token:
            token = settings.official_voice_token.strip()
            headers["Authorization"] = (
                token if token.lower().startswith("bearer ") else f"Bearer {token}"
            )

        self._client = aiohttp.ClientSession()
        self._ws = await self._client.ws_connect(
            settings.official_voice_ws_url,
            headers=headers,
            timeout=15,
            heartbeat=20,
        )
        await self._send_official_hello()
        hello = await self._ws.receive(timeout=15)
        if hello.type != aiohttp.WSMsgType.TEXT:
            raise RuntimeError(f"unexpected official hello frame: {hello.type}")
        payload = json.loads(hello.data)
        self._official_session_id = str(payload.get("session_id") or "")
        logger.info(
            "Official voice connected (device=%s, official_session=%s)",
            self.session.device_id,
            self._official_session_id,
        )
        self._recv_task = asyncio.create_task(self._recv_loop())

    async def send_json(self, payload: dict[str, Any]) -> None:
        await self.connect()
        if not self._ws or self._ws.closed:
            raise RuntimeError("official voice websocket is not connected")
        outbound = dict(payload)
        if self._official_session_id:
            outbound["session_id"] = self._official_session_id
        async with self._send_lock:
            await self._ws.send_str(json.dumps(outbound, ensure_ascii=False))

    async def send_audio(self, data: bytes) -> None:
        await self.connect()
        if not self._ws or self._ws.closed:
            raise RuntimeError("official voice websocket is not connected")
        async with self._send_lock:
            await self._ws.send_bytes(data)

    async def close(self) -> None:
        self._closed = True
        await self._teardown_ws()

    async def _teardown_ws(self) -> None:
        task = self._recv_task
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
        self._recv_task = None

        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None

        if self._client and not self._client.closed:
            await self._client.close()
        self._client = None

    async def _background_reconnect(self) -> None:
        """Pre-connect upstream after a per-turn goodbye so the next turn is instant."""
        await asyncio.sleep(0.3)
        try:
            await self.connect()
        except Exception as exc:
            logger.warning("Official voice background reconnect failed: %s", exc)

    async def _send_official_hello(self) -> None:
        if not self._ws:
            raise RuntimeError("official voice websocket is not connected")
        hello = {
            "type": "hello",
            "version": 3,
            "features": {"mcp": True},
            "transport": "websocket",
            "audio_params": {
                "format": "opus",
                "sample_rate": 16000,
                "channels": 1,
                "frame_duration": 60,
            },
        }
        await self._ws.send_str(json.dumps(hello, ensure_ascii=False))

    async def _recv_loop(self) -> None:
        assert self._ws is not None
        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._forward_text(msg.data)
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    await self._forward_binary(msg.data)
                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED):
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    raise RuntimeError(self._ws.exception())
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.error("Official voice receive loop failed: %s", exc)
        finally:
            try:
                await self._finish_tts_if_needed()
            except Exception as exc:
                logger.error("Failed to finish official TTS after upstream close: %s", exc)
            logger.info("Official voice disconnected (device=%s)", self.session.device_id)

    async def _forward_text(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Official voice sent non-JSON text: %r", raw[:80])
            return

        if payload.get("type") == "hello":
            return

        payload["session_id"] = self.session.session_id
        msg_type = payload.get("type")
        if msg_type == "goodbye":
            logger.info(
                "Official goodbye ignored to keep local device session alive (device=%s)",
                self.session.device_id,
            )
            await self._finish_tts_if_needed()
            await self._teardown_ws()
            asyncio.create_task(self._background_reconnect())
            return

        if msg_type == "tts":
            state = payload.get("state")
            text = payload.get("text", "")
            logger.info(
                "Official TTS: state=%s text=%s",
                state,
                str(text)[:80],
            )
            if state == "start":
                self._tts_started = True
                self._reset_turn_stats()
                self.session.state = DeviceState.SPEAKING
            elif state == "sentence_start":
                if not self._tts_started:
                    await self._send_device_payload({"type": "tts", "state": "start"})
                    self._tts_started = True
                    self._reset_turn_stats()
                self.session.state = DeviceState.SPEAKING
            elif state == "sentence_end":
                # The board arms a timeout on sentence_end; deliver it near the
                # real end of that sentence's audio, not when the (possibly
                # bursty) frames happened to arrive.
                await self._hold_for_drain(margin=-0.5)
            elif state == "stop":
                await self._hold_for_drain(margin=0.2)
                backlog = self._playback_until - time.monotonic()
                logger.info(
                    "Official TTS turn summary: frames=%d (%.1fs audio), gaps>150ms=%d, max_gap=%.2fs, backlog_at_stop=%.2fs",
                    self._downlink_binary_frames,
                    self._downlink_binary_frames * 0.06,
                    self._turn_gap_count,
                    self._turn_gap_max,
                    backlog,
                )
                self._tts_started = False
                self.session.state = DeviceState.IDLE
        elif msg_type == "stt":
            logger.info(
                "Official STT (device=%s): %s",
                self.session.device_id,
                payload.get("text", ""),
            )

        await self._send_device_payload(payload)

    async def _forward_binary(self, data: bytes) -> None:
        """Forward official TTS opus frames untouched and at arrival pace.

        The official cloud already streams at ~60ms per frame and the board
        has a deep (256-slot) playback queue. Re-pacing frames here only adds
        timer jitter that starves the board's player (choppy audio).
        """
        if not self._tts_started:
            await self._send_device_payload({"type": "tts", "state": "start"})
            self._tts_started = True
            self._reset_turn_stats()
            self.session.state = DeviceState.SPEAKING

        now = time.monotonic()
        if self._turn_last_frame_at > 0:
            gap = now - self._turn_last_frame_at
            if gap > 0.15:
                self._turn_gap_count += 1
                self._turn_gap_max = max(self._turn_gap_max, gap)
        self._turn_last_frame_at = now
        self._playback_until = max(self._playback_until, now) + 0.06
        self._downlink_binary_frames += 1
        if self._downlink_binary_frames % 20 == 0:
            logger.debug(
                "Official TTS audio forwarded: frame=%d bytes=%d device=%s",
                self._downlink_binary_frames,
                len(data),
                self.session.device_id,
            )

        if self.device_ws.client_state == WebSocketState.CONNECTED:
            async with self.session.device_send_lock:
                await self.device_ws.send_bytes(data)

    async def _send_device_payload(self, payload: dict[str, Any]) -> None:
        if self.device_ws.client_state == WebSocketState.CONNECTED:
            outbound = {"session_id": self.session.session_id, **payload}
            async with self.session.device_send_lock:
                await self.device_ws.send_text(json.dumps(outbound, ensure_ascii=False))

    async def _finish_tts_if_needed(self) -> None:
        if not self._tts_started:
            return
        await self._hold_for_drain(margin=0.2)
        await self._send_device_payload({"type": "tts", "state": "stop"})
        self._tts_started = False
        self.session.state = DeviceState.IDLE

    def _reset_turn_stats(self) -> None:
        self._downlink_binary_frames = 0
        self._playback_until = time.monotonic()
        self._turn_last_frame_at = 0.0
        self._turn_gap_count = 0
        self._turn_gap_max = 0.0

    async def _hold_for_drain(self, *, margin: float) -> None:
        """Sleep until the board's queued audio is (nearly) played out.

        margin > 0 waits past the end; margin < 0 leaves that much backlog.
        """
        delay = self._playback_until - time.monotonic() + margin
        if delay > 0:
            await asyncio.sleep(delay)
