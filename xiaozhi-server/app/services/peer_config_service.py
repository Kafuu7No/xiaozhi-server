"""Push board2 address and water-linkage settings to board1 over WebSocket.

board1 runs the cat-meow-to-water trigger locally and sends pump commands
straight to board2 over UDP. The cloud only tells board1 the current board2
IP candidates and the dashboard settings that gate the feature.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from . import water_service
from .session_manager import session_manager
from .udp_hardware_bridge import udp_hardware_bridge

logger = logging.getLogger("xz.peer")


def build_peer_config(
    water_settings: dict[str, Any], board2_ips: list[str], port: int
) -> dict[str, Any]:
    """Build the board1 ``peer_config`` WebSocket payload."""
    return {
        "type": "peer_config",
        "board2_ips": list(board2_ips),
        "port": int(port),
        "autoOnMeow": bool(water_settings.get("autoOnMeow")),
        "delaySeconds": int(water_settings.get("delaySeconds") or 15),
    }


async def push_peer_config(db: AsyncSession) -> bool:
    """Push current peer_config to board1. Return False when board1 is offline."""
    pair = session_manager.primary_session()
    if pair:
        session, _ = pair
        if session.voice_turn_running:
            logger.debug("peer_config push skipped during voice turn: %s", session.session_id)
            return False

    settings = get_settings()
    water_settings = await water_service.get_settings(db)
    board2_ips = udp_hardware_bridge.candidate_ips()
    payload = build_peer_config(water_settings, board2_ips, settings.udp_device_port)
    sent = await session_manager.send_to_primary(payload)
    if sent:
        logger.info("peer_config pushed to board1: %s", payload)
    return sent
