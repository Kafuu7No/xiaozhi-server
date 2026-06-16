"""Water-pump REST API: manual control, schedules and settings."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services import peer_config_service, water_service
from ..services.session_manager import session_manager
from ..services.udp_hardware_bridge import DEVICE_ID as UDP_DEVICE_ID
from ..services.udp_hardware_bridge import udp_hardware_bridge

router = APIRouter()


def _get_primary_session():
    return session_manager.primary_session()


def _primary_device_id() -> str:
    current = _get_primary_session()
    return current[0].device_id if current else "unknown-device"


def _record_device_id(transport: str | None) -> str:
    current = _get_primary_session()
    if current:
        return current[0].device_id
    if transport == "udp":
        return UDP_DEVICE_ID
    return "unknown-device"


async def _send_device_payload(payload: dict[str, Any]) -> bool:
    return await session_manager.send_to_primary(payload)


@router.get("/water/records")
async def get_water_records(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await water_service.list_records(db)


@router.get("/water/records/paged")
async def get_water_records_paged(
    page: int = 1, page_size: int = 20, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Paged pump records (newest first), max 99 pages."""
    return await water_service.list_records_paged(db, page=page, page_size=page_size)


@router.get("/water/usage")
async def get_water_usage(
    granularity: str = "day", db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Water usage aggregated by hour (last 24h) or day (last 7d) for the chart."""
    gran = "hour" if granularity == "hour" else "day"
    return {"granularity": gran, "series": await water_service.usage_series(db, granularity=gran)}


class PumpControlRequest(BaseModel):
    action: str = Field(pattern="^(start|stop)$")
    duration: float = 15
    trigger_type: str = "manual"


@router.post("/water/pump/control")
async def post_water_pump_control(
    req: PumpControlRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    if req.action == "start":
        # 水泵在 board2(UDP)，固定优先走 UDP 桥；WS 设备(board1)没有水泵，仅兜底。
        sent = udp_hardware_bridge.send_pump_start(req.duration)
        transport = "udp" if sent else None
        if not sent:
            sent = await _send_device_payload(
                water_service.build_pump_command("start", req.duration)
            )
            transport = "websocket" if sent else None
        record = await water_service.create_pump_record(
            db,
            device_id=_record_device_id(transport),
            duration_seconds=req.duration,
            trigger_type=req.trigger_type,
        )
        return {"status": "sent" if sent else "mocked", "transport": transport, "record": record}

    sent = udp_hardware_bridge.send_pump_stop()
    transport = "udp" if sent else None
    if not sent:
        sent = await _send_device_payload(water_service.build_pump_command("stop"))
        transport = "websocket" if sent else None
    record = await water_service.stop_active_pump(db)
    return {
        "status": "sent" if sent else "mocked",
        "transport": transport,
        "stopped": record is not None,
        "record": record,
    }


@router.get("/water/schedule")
async def get_water_schedules(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await water_service.list_schedules(db)


class ScheduleCreateRequest(BaseModel):
    label: str = "未命名计划"
    time: str
    duration_seconds: float = 15
    enabled: bool = True


@router.post("/water/schedule")
async def post_water_schedule(
    req: ScheduleCreateRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    return await water_service.create_schedule(
        db,
        label=req.label,
        time=req.time,
        duration_seconds=req.duration_seconds,
        enabled=req.enabled,
    )


class ScheduleUpdateRequest(BaseModel):
    label: str | None = None
    time: str | None = None
    duration_seconds: float | None = None
    enabled: bool | None = None


@router.put("/water/schedule/{schedule_id}")
async def put_water_schedule(
    schedule_id: int,
    req: ScheduleUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    updated = await water_service.update_schedule(db, schedule_id, req.model_dump())
    if updated is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return updated


@router.delete("/water/schedule/{schedule_id}")
async def delete_water_schedule(
    schedule_id: int, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    removed = await water_service.delete_schedule(db, schedule_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"status": "deleted", "id": schedule_id}


@router.get("/water/settings")
async def get_water_settings(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return await water_service.get_settings(db)


class SettingsRequest(BaseModel):
    autoOnMeow: bool | None = None
    delaySeconds: int | None = None


@router.put("/water/settings")
async def put_water_settings(
    req: SettingsRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    saved = await water_service.save_settings(
        db, auto_on_meow=req.autoOnMeow, delay_seconds=req.delaySeconds
    )
    await peer_config_service.push_peer_config(db)
    return saved
