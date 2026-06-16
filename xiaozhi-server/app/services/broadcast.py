"""Dashboard broadcast service.

Maintains the set of connected dashboard WebSocket clients and provides
helper functions to push events to all of them.
"""

import json
import logging
from fastapi import WebSocket

logger = logging.getLogger("xz.broadcast")

# All connected /ws/dashboard clients
dashboard_clients: set[WebSocket] = set()


async def broadcast(event: str, data: dict) -> None:
    """Send an event to all connected dashboard clients."""
    message = json.dumps({"event": event, "data": data}, default=str)
    dead: set[WebSocket] = set()
    for ws in dashboard_clients:
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    dashboard_clients.difference_update(dead)
    if dead:
        logger.debug("Removed %d dead dashboard connections", len(dead))
