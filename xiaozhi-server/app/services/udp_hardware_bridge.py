"""UDP bridge for the standalone key_camera firmware.

The firmware listens for compact UDP commands on port 8848 and sends raw JPEG
chunks back to the PC hotspot address. This service lets the existing REST API
control that firmware without changing the frontend.
"""

from __future__ import annotations

import asyncio
import logging
import re
import socket
import subprocess
import time

from ..core.config import get_settings
from ..core.database import async_session
from . import camera_service
from .broadcast import broadcast

logger = logging.getLogger("xz.udp.hw")

_MAC_RE = re.compile(r"^([0-9a-f]{2}[:-]){5}[0-9a-f]{2}$", re.IGNORECASE)


def _normalize_mac(mac: str) -> str:
    return mac.replace("-", ":").lower().strip()


def arp_ips_for_mac(mac: str, *, subnet_prefix: str | None = None) -> list[str]:
    """Return IPv4 addresses currently mapped to ``mac`` in the OS ARP table.

    The board's DHCP IP changes across reboots/networks; resolving by its fixed
    MAC lets us reach it without manual re-priming. Multiple (incl. stale) entries
    may exist, so callers send to all candidates — only the live one responds.
    """
    if not mac or not _MAC_RE.match(_normalize_mac(mac)):
        return []
    want = _normalize_mac(mac)
    try:
        out = subprocess.run(
            ["arp", "-a"], capture_output=True, text=True, timeout=3
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("arp -a failed: %s", exc)
        return []

    ips: list[str] = []
    ip_re = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3})\s+([0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){5})")
    for line in out.splitlines():
        m = ip_re.search(line)
        if not m:
            continue
        ip, found_mac = m.group(1), _normalize_mac(m.group(2))
        if found_mac == want and (subnet_prefix is None or ip.startswith(subnet_prefix)):
            if ip not in ips:
                ips.append(ip)
    return ips

DEVICE_ID = "udp-key-camera"
CMD_CAPTURE = b"\x01"
CMD_RELAY_STOP = b"\x11"
JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"
MAX_PUMP_MS = 600_000


def build_pump_start_packet(duration_seconds: float | int | None) -> bytes:
    """Build ``0x10 + little-endian duration_ms`` for the relay/pump."""
    seconds = float(duration_seconds or 0)
    duration_ms = max(0, min(MAX_PUMP_MS, int(seconds * 1000)))
    return b"\x10" + duration_ms.to_bytes(4, "little", signed=False)


class UdpPhotoAssembler:
    """Accumulate raw UDP JPEG chunks until an end marker is seen."""

    def __init__(self, *, max_bytes: int, idle_timeout: float) -> None:
        self.max_bytes = max_bytes
        self.idle_timeout = idle_timeout
        self.buffer = bytearray()
        self.last_packet_at = 0.0

    def reset(self) -> None:
        self.buffer.clear()
        self.last_packet_at = 0.0

    def feed(self, data: bytes) -> bytes | None:
        now = time.monotonic()
        if self.buffer and now - self.last_packet_at > self.idle_timeout:
            logger.warning("Dropping stale UDP photo buffer (%d bytes)", len(self.buffer))
            self.reset()

        if not self.buffer:
            start = data.find(JPEG_SOI)
            if start < 0:
                return None
            data = data[start:]

        self.buffer.extend(data)
        self.last_packet_at = now

        if len(self.buffer) > self.max_bytes:
            logger.warning("Dropping oversized UDP photo buffer (%d bytes)", len(self.buffer))
            self.reset()
            return None

        end = self.buffer.find(JPEG_EOI)
        if end < 0:
            return None

        photo = bytes(self.buffer[: end + len(JPEG_EOI)])
        self.reset()
        return photo


class _BridgeProtocol(asyncio.DatagramProtocol):
    def __init__(self, bridge: "UdpHardwareBridge") -> None:
        self.bridge = bridge

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.bridge.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.bridge.handle_datagram(data, addr)

    def error_received(self, exc: Exception) -> None:
        logger.warning("UDP bridge socket error: %s", exc)

    def connection_lost(self, exc: Exception | None) -> None:
        self.bridge.transport = None
        if exc:
            logger.warning("UDP bridge closed: %s", exc)


class UdpHardwareBridge:
    def __init__(self) -> None:
        self.transport: asyncio.DatagramTransport | None = None
        self.assembler: UdpPhotoAssembler | None = None
        self.last_sender: tuple[str, int] | None = None
        self.last_photo_at: float | None = None
        self.enabled = False

    async def start(self) -> None:
        settings = get_settings()
        self.enabled = bool(settings.udp_hardware_enabled)
        if not self.enabled:
            logger.info("UDP hardware bridge disabled")
            return

        self.assembler = UdpPhotoAssembler(
            max_bytes=settings.udp_photo_max_bytes,
            idle_timeout=settings.udp_photo_idle_timeout,
        )

        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Firmware blasts ~33 back-to-back datagrams per photo with no pacing;
        # a large receive buffer keeps the burst from overflowing and dropping
        # the trailing packets (which showed up as a grey band at the bottom).
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)  # 1 MiB
        except OSError as exc:
            logger.warning("Could not enlarge UDP SO_RCVBUF: %s", exc)
        sock.bind((settings.udp_listen_host, settings.udp_listen_port))

        await loop.create_datagram_endpoint(lambda: _BridgeProtocol(self), sock=sock)
        logger.info(
            "UDP hardware bridge listening on %s:%d, sending to %s:%d",
            settings.udp_listen_host,
            settings.udp_listen_port,
            settings.udp_device_host,
            settings.udp_device_port,
        )

    async def stop(self) -> None:
        if self.transport:
            self.transport.close()
            self.transport = None

    def is_ready(self) -> bool:
        return self.enabled and self.transport is not None

    def send_capture(self) -> bool:
        return self._send(CMD_CAPTURE)

    def send_pump_start(self, duration_seconds: float | int | None) -> bool:
        return self._send(build_pump_start_packet(duration_seconds))

    def send_pump_stop(self) -> bool:
        return self._send(CMD_RELAY_STOP)

    def candidate_ips(self) -> list[str]:
        """Public view of the board2 candidate IPs (for peer_config push)."""
        return self._candidate_ips()

    def _candidate_ips(self) -> list[str]:
        """All plausible current IPs for the board.

        The firmware's lwIP does not accept subnet-directed broadcast, and its
        DHCP IP changes across reboots/networks, so we collect every candidate
        and send to all of them: the address it last uploaded a photo from
        (most reliable), every ARP entry for its MAC (survives reboots without
        manual priming), and the configured fallback. Stale IPs simply drop the
        datagram; only the live board acts on it.
        """
        settings = get_settings()
        ips: list[str] = []
        if self.last_sender:
            ips.append(self.last_sender[0])
        prefix = (settings.udp_device_host.rsplit(".", 1)[0] + ".") if settings.udp_device_host else None
        for ip in arp_ips_for_mac(settings.udp_device_mac, subnet_prefix=prefix):
            ips.append(ip)
        if settings.udp_device_host:
            ips.append(settings.udp_device_host)
        # dedup, preserve order
        seen: set[str] = set()
        return [ip for ip in ips if ip and not (ip in seen or seen.add(ip))]

    def _send(self, payload: bytes) -> bool:
        settings = get_settings()
        if not settings.udp_hardware_enabled:
            return False

        port = settings.udp_device_port
        targets = self._candidate_ips()
        if not targets:
            logger.warning("UDP hardware command has no target IP")
            return False

        sent_any = False
        for ip in targets:
            try:
                if self.transport:
                    self.transport.sendto(payload, (ip, port))
                else:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                        sock.sendto(payload, (ip, port))
                sent_any = True
            except OSError as exc:
                logger.debug("UDP send to %s:%d failed: %s", ip, port, exc)
        if sent_any:
            logger.info("UDP hardware command sent: %s -> %s", payload.hex(), targets)
        else:
            logger.error("UDP hardware command failed for all targets: %s", targets)
        return sent_any

    def handle_datagram(self, data: bytes, addr: tuple[str, int]) -> None:
        if not self.assembler:
            return
        self.last_sender = addr
        photo = self.assembler.feed(data)
        if photo is not None:
            asyncio.create_task(self._store_photo(photo, addr))

    async def _store_photo(self, image_bytes: bytes, addr: tuple[str, int]) -> None:
        try:
            async with async_session() as db:
                photo = await camera_service.save_photo(
                    db,
                    device_id=f"{DEVICE_ID}-{addr[0]}",
                    image_bytes=image_bytes,
                )
            self.last_photo_at = time.time()
            await broadcast("camera_photo", photo)
            logger.info("UDP photo stored from %s:%d (%d bytes)", addr[0], addr[1], len(image_bytes))
        except Exception:
            logger.exception("Failed to store UDP photo from %s:%d", addr[0], addr[1])


udp_hardware_bridge = UdpHardwareBridge()
