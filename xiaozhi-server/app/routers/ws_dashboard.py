"""WebSocket endpoint for the Vue frontend dashboard.

Clients connect to /ws/dashboard and receive real-time push events
whenever the device sends data.
"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.broadcast import dashboard_clients

logger = logging.getLogger("xz.ws_dash")
router = APIRouter()


@router.websocket("/ws/dashboard")
async def websocket_dashboard(ws: WebSocket):
    """Frontend dashboard WebSocket.  Push-only from server to browser."""
    await ws.accept()
    dashboard_clients.add(ws)
    logger.info("Dashboard client connected (total=%d)", len(dashboard_clients))
    try:
        while True:
            # Keep connection alive; dashboard sends nothing meaningful
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("Dashboard ws error: %s", e)
    finally:
        dashboard_clients.discard(ws)
        logger.info("Dashboard client disconnected (total=%d)", len(dashboard_clients))
