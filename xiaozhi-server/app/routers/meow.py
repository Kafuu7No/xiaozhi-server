"""Meow REST API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services import meow_service
from ..services.session_manager import session_manager

router = APIRouter()

meow_control_state: dict[str, Any] = {
    "desired_enabled": False,
    "device_enabled": False,
    "status": "stopped",
    "message": "",
    "result": None,
    "updated_at": None,
}


def get_meow_control_state() -> dict[str, Any]:
    return dict(meow_control_state)


async def update_meow_status(
    *,
    enabled: bool,
    result: int | None = None,
    message: str = "",
    device_id: str = "",
) -> dict[str, Any]:
    from datetime import datetime

    meow_control_state.update(
        {
            "device_enabled": bool(enabled),
            "status": "running" if enabled else "stopped",
            "message": message or "",
            "result": result,
            "updated_at": datetime.now().isoformat(),
            "device_id": device_id,
        }
    )
    payload = get_meow_control_state()
    from ..services.broadcast import broadcast

    await broadcast("meow_status", payload)
    return payload


async def _send_device_payload(payload: dict[str, Any]) -> bool:
    return await session_manager.send_to_primary(payload)


@router.get("/meow/events")
async def get_meow_events(
    hours: int = 24,
    is_cat: bool | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await meow_service.get_events(db, hours=hours, is_cat=is_cat)


@router.get("/meow/stats")
async def get_meow_stats(db: AsyncSession = Depends(get_db)) -> dict:
    stats = await meow_service.get_stats(db)
    stats["detection_enabled"] = bool(meow_control_state["device_enabled"])
    stats["desired_enabled"] = bool(meow_control_state["desired_enabled"])
    stats["device_enabled"] = bool(meow_control_state["device_enabled"])
    stats["control_status"] = meow_control_state["status"]
    stats["control_message"] = meow_control_state["message"]
    stats["control_result"] = meow_control_state["result"]
    stats["control_updated_at"] = meow_control_state["updated_at"]
    return stats


class MeowControlRequest(BaseModel):
    action: str = Field(pattern="^(start|stop)$")


@router.post("/meow/control")
async def post_meow_control(req: MeowControlRequest) -> dict[str, Any]:
    enabled = req.action == "start"
    meow_control_state.update(
        {
            "desired_enabled": enabled,
            "status": "command_sent",
            "message": "",
            "result": None,
        }
    )
    sent = await _send_device_payload({"type": "meow_control", "action": req.action})
    if not sent:
        meow_control_state.update(
            {
                "device_enabled": False,
                "status": "device_offline",
                "message": "device_offline",
            }
        )
    return {
        "status": "sent" if sent else "mocked",
        "detection_enabled": bool(meow_control_state["device_enabled"]),
        "desired_enabled": enabled,
        "device_enabled": bool(meow_control_state["device_enabled"]),
        "control_status": meow_control_state["status"],
        "control_message": meow_control_state["message"],
        "control_result": meow_control_state["result"],
        "device_connected": sent,
    }
