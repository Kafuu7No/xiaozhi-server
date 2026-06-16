"""TCP receiver for key_camera photo uploads.

UDP photo upload dropped ~13% of packets on congested 2.4GHz (corrupt images,
and a lost final packet meant the photo was never saved). The firmware now
streams each JPEG over TCP using a simple length-prefixed framing:

    [4-byte little-endian length N][N bytes of JPEG]...

TCP guarantees in-order, lossless delivery, so every photo arrives complete.
Commands to the board still go out over UDP (see ``udp_hardware_bridge``); this
module only handles the inbound photo stream.
"""

from __future__ import annotations

import asyncio
import logging
import struct

from ..core.config import get_settings
from ..core.database import async_session
from . import camera_service
from .broadcast import broadcast
from .udp_hardware_bridge import DEVICE_ID, udp_hardware_bridge

logger = logging.getLogger("xz.tcp.photo")


class TcpPhotoReceiver:
    def __init__(self) -> None:
        self.server: asyncio.AbstractServer | None = None
        self.enabled = False

    async def start(self) -> None:
        settings = get_settings()
        self.enabled = bool(settings.tcp_photo_enabled)
        if not self.enabled:
            logger.info("TCP photo receiver disabled")
            return
        self.server = await asyncio.start_server(
            self._handle_client, settings.tcp_listen_host, settings.tcp_listen_port
        )
        logger.info(
            "TCP photo receiver listening on %s:%d",
            settings.tcp_listen_host,
            settings.tcp_listen_port,
        )

    async def stop(self) -> None:
        if self.server:
            self.server.close()
            try:
                await self.server.wait_closed()
            except Exception:  # noqa: BLE001
                pass
            self.server = None

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        settings = get_settings()
        peer = writer.get_extra_info("peername")
        ip = peer[0] if peer else "?"
        # Let outbound commands (pump/capture) target this board even before it
        # uploads over UDP — the TCP peer IP is the live board address.
        udp_hardware_bridge.last_sender = (ip, settings.udp_device_port)
        logger.info("TCP photo client connected: %s", ip)

        max_bytes = settings.udp_photo_max_bytes
        try:
            while True:
                header = await reader.readexactly(4)
                (length,) = struct.unpack("<I", header)
                if length == 0 or length > max_bytes:
                    logger.warning("TCP photo bad length %d from %s, closing", length, ip)
                    break
                image_bytes = await reader.readexactly(length)
                await self._store_photo(image_bytes, ip)
        except asyncio.IncompleteReadError:
            logger.info("TCP photo client closed: %s", ip)
        except Exception:  # noqa: BLE001
            logger.exception("TCP photo receive error from %s", ip)
        finally:
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass

    async def _store_photo(self, image_bytes: bytes, ip: str) -> None:
        async with async_session() as db:
            photo = await camera_service.save_photo(
                db, device_id=f"{DEVICE_ID}-{ip}", image_bytes=image_bytes
            )
        await broadcast("camera_photo", photo)
        logger.info("TCP photo stored from %s (%d bytes)", ip, len(image_bytes))


tcp_photo_receiver = TcpPhotoReceiver()
