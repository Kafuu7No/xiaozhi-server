"""Manages active device sessions.

Simple in-memory store for now. Could be backed by Redis later
for multi-process deployment.
"""

import json
import logging
from typing import Optional
from fastapi import WebSocket
from ..models.protocol import DeviceSession

logger = logging.getLogger("xz.session")


class SessionManager:
    """Tracks active WebSocket sessions by session_id."""
    
    def __init__(self):
        # session_id -> (DeviceSession, WebSocket)
        self._sessions: dict[str, tuple[DeviceSession, WebSocket]] = {}
    
    def create_session(self, ws: WebSocket, device_id: str, client_id: str) -> DeviceSession:
        session = DeviceSession(device_id=device_id, client_id=client_id)
        self._sessions[session.session_id] = (session, ws)
        logger.info(
            "Session created: %s (device=%s)", 
            session.session_id, device_id or "unknown"
        )
        return session
    
    def get_session(self, session_id: str) -> Optional[tuple[DeviceSession, WebSocket]]:
        return self._sessions.get(session_id)
    
    def remove_session(self, session_id: str) -> None:
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("Session removed: %s", session_id)
    
    def primary_session(self) -> Optional[tuple[DeviceSession, WebSocket]]:
        """Return the first active session pair (board1 is the only WS device), or None."""
        for pair in self._sessions.values():
            return pair
        return None

    async def send_to_primary(self, payload: dict) -> bool:
        """Send a JSON payload to the primary (board1) WS device.

        Returns False when no device is connected.
        """
        pair = self.primary_session()
        if not pair:
            return False
        session, ws = pair
        async with session.device_send_lock:
            await ws.send_text(json.dumps(payload, ensure_ascii=False))
        return True

    @property
    def active_count(self) -> int:
        return len(self._sessions)


# Global singleton
session_manager = SessionManager()
