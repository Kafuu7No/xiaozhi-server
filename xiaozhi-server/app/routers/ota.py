"""Firmware OTA compatibility endpoint.

The device firmware posts its boot metadata here before opening the
/xiaozhi/v1/ WebSocket. For local development we only need to acknowledge
that request so the firmware proceeds to the WebSocket handshake.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/xiaozhi")


@router.post("/ota/")
async def ota_probe(request: Request) -> dict:
    body = await request.json()
    return {
        "status": "ok",
        "mqtt": None,
        "websocket": {
            "url": "/xiaozhi/v1/",
        },
        "server_time": None,
        "device": {
            "mac_address": body.get("mac_address"),
            "uuid": body.get("uuid"),
        },
    }
