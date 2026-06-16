"""UDP discovery service for local XiaoZhi devices.

Devices broadcast a tiny discovery packet after joining Wi-Fi.  The cloud
server replies from the interface that received the broadcast, so the device can
learn the current PC IP without recompiling firmware when the LAN changes.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ..core.config import get_settings

DISCOVERY_REQUEST = "XIAOZHI_DISCOVER_V1"
DISCOVERY_RESPONSE = "XIAOZHI_CLOUD_V1"

logger = logging.getLogger("xz.discovery")

_transport: Optional[asyncio.DatagramTransport] = None


class DiscoveryProtocol(asyncio.DatagramProtocol):
    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        message = data.decode("utf-8", errors="ignore").strip()
        if message != DISCOVERY_REQUEST:
            return

        settings = get_settings()
        payload = f"{DISCOVERY_RESPONSE} port={settings.port}".encode("utf-8")
        if self.transport:
            self.transport.sendto(payload, addr)
            logger.info("Discovery reply sent to %s:%d", addr[0], addr[1])

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def error_received(self, exc: Exception) -> None:
        logger.warning("Discovery UDP error: %s", exc)


async def start_discovery_service() -> None:
    global _transport
    settings = get_settings()
    if not settings.discovery_enabled or _transport is not None:
        return

    loop = asyncio.get_running_loop()
    try:
        transport, _ = await loop.create_datagram_endpoint(
            DiscoveryProtocol,
            local_addr=("0.0.0.0", settings.discovery_port),
            allow_broadcast=True,
        )
    except Exception as exc:
        logger.warning("Discovery service unavailable on UDP %d: %s", settings.discovery_port, exc)
        return

    _transport = transport  # type: ignore[assignment]
    logger.info("Discovery service listening on UDP %d", settings.discovery_port)


async def stop_discovery_service() -> None:
    global _transport
    if _transport is None:
        return
    _transport.close()
    _transport = None
    logger.info("Discovery service stopped")
