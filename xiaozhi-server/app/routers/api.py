"""Shared dashboard REST API endpoints unrelated to sprint 2/3 sensor/meow routes."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.database import ConversationLog
from ..services import camera_service, settings_service
from ..services.session_manager import session_manager
from ..services.udp_hardware_bridge import udp_hardware_bridge

logger = logging.getLogger("xz.api")
router = APIRouter(prefix="/api")


def _get_primary_session():
    sessions = list(session_manager._sessions.values())
    if not sessions:
        return None
    return sessions[0]


async def _send_device_payload(payload: dict[str, Any]) -> bool:
    return await session_manager.send_to_primary(payload)


@router.get("/device/status")
async def get_device_status() -> dict:
    current = _get_primary_session()
    if not current:
        return {"device_id": None, "state": "disconnected", "iot_states": [], "connected": False}

    session, _ = current
    return {
        "device_id": session.device_id,
        "state": session.state.value,
        "iot_states": session.iot_states,
        "connected": True,
    }


@router.post("/camera/capture")
async def post_camera_capture() -> dict[str, Any]:
    """Tell the camera board (board2, UDP) to take a photo and upload it.

    The camera lives on the UDP board, so prefer the UDP bridge. The WS device
    (board1: meow/sensor) has no camera, so only fall back to it if the UDP
    bridge is unavailable.
    """
    sent = udp_hardware_bridge.send_capture()
    transport = "udp" if sent else None
    if not sent:
        sent = await _send_device_payload(camera_service.build_capture_command())
        transport = "websocket" if sent else None
    if not sent:
        raise HTTPException(status_code=503, detail="No device connected")
    logger.info("Camera capture command sent to device via %s", transport)
    return {"status": "capture_requested", "transport": transport}


@router.post("/camera/upload")
async def post_camera_upload(
    request: Request,
    device_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Receive a JPEG photo (raw request body) uploaded by the device."""
    image_bytes = await request.body()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image body")

    resolved_device_id = device_id or request.headers.get("device-id", "") or "unknown-device"
    return await camera_service.save_photo(
        db, device_id=resolved_device_id, image_bytes=image_bytes
    )


@router.get("/camera/latest")
async def get_camera_latest(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Return the most recently captured photo for the dashboard."""
    photo = await camera_service.get_latest_photo(db)
    return {
        "photo": photo,
        "device_connected": _get_primary_session() is not None or udp_hardware_bridge.is_ready(),
    }


@router.get("/camera/photos")
async def get_camera_photos(
    page: int = 1, page_size: int = 15, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Return one page of photos (newest first), max 99 pages, for the gallery."""
    return await camera_service.list_photos_paged(db, page=page, page_size=page_size)


@router.delete("/camera/photos/{photo_id}")
async def delete_camera_photo(
    photo_id: int, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Delete a stored photo (DB row + file)."""
    removed = await camera_service.delete_photo(db, photo_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Photo not found")
    return {"status": "deleted", "id": photo_id}


@router.get("/settings")
async def get_app_settings(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Return all adjustable app settings (thresholds + water linkage)."""
    return await settings_service.get_settings(db)


class AppSettingsRequest(BaseModel):
    meowThreshold: float | None = None
    meowMinConfidence: float | None = None
    tempMax: float | None = None
    humidMin: float | None = None
    humidMax: float | None = None
    autoOnMeow: bool | None = None
    delaySeconds: int | None = None


@router.put("/settings")
async def put_app_settings(
    req: AppSettingsRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Apply a partial update to the app settings."""
    return await settings_service.save_settings(db, req.model_dump())


class IotCommandRequest(BaseModel):
    device_name: str
    method: str
    parameters: dict[str, Any] = {}


@router.post("/iot/command")
async def send_iot_command(req: IotCommandRequest) -> dict:
    payload = {
        "type": "iot",
        "commands": [
            {
                "name": req.device_name,
                "method": req.method,
                "parameters": req.parameters,
            }
        ],
    }
    sent = await _send_device_payload(payload)
    if not sent:
        raise HTTPException(status_code=503, detail="No device connected")

    logger.info("IoT command sent: %s.%s(%s)", req.device_name, req.method, req.parameters)
    return {"status": "sent"}


class MeowWaterFireRequest(BaseModel):
    duration: int = 3


@router.post("/debug/meow-water/fire")
async def debug_meow_water_fire(req: MeowWaterFireRequest) -> dict[str, Any]:
    duration = max(1, min(600, int(req.duration or 3)))
    sent = await _send_device_payload(
        {"type": "meow_water_fire", "duration": duration}
    )
    if not sent:
        raise HTTPException(status_code=503, detail="No board1 session connected")
    logger.info("Debug meow_water_fire sent to board1: duration=%ss", duration)
    return {"status": "sent", "duration": duration}


@router.get("/conversations")
async def get_conversations(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await db.execute(
        select(ConversationLog)
        .order_by(ConversationLog.recorded_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "role": row.role,
            "content": row.content,
            "emotion": row.emotion,
            "recorded_at": row.recorded_at.isoformat(),
        }
        for row in reversed(rows)
    ]
