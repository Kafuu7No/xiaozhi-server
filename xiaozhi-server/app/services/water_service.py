"""Water-pump service: volume estimation, serialization, pump command, and
persistence for pump records, schedules and settings."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import WaterRecord, WaterSchedule
from . import settings_service

logger = logging.getLogger("xz.water")

# Rough estimate: the pump delivers ~3 ml of water per second of runtime.
ML_PER_SECOND = 3


def estimate_volume_ml(duration_seconds: float) -> int:
    """Estimate dispensed water volume from pump runtime."""
    return round((duration_seconds or 0) * ML_PER_SECOND)


def serialize_record(record: WaterRecord) -> dict[str, Any]:
    """Serialize a pump record into the API response shape."""
    return {
        "id": record.id,
        "device_id": record.device_id,
        "trigger_type": record.trigger_type,
        "duration_seconds": int(record.duration_seconds or 0),
        "volume_ml": estimate_volume_ml(record.duration_seconds),
        "started_at": record.started_at.isoformat() if record.started_at else None,
        "ended_at": record.ended_at.isoformat() if record.ended_at else None,
    }


def serialize_schedule(schedule: WaterSchedule) -> dict[str, Any]:
    """Serialize a water schedule into the API response shape."""
    return {
        "id": schedule.id,
        "label": schedule.label,
        "time": schedule.time,
        "duration_seconds": int(schedule.duration_seconds or 0),
        "enabled": schedule.enabled,
    }


def build_pump_command(action: str, duration: float | None = None) -> dict[str, Any]:
    """Build the WebSocket payload that controls the device water pump."""
    command: dict[str, Any] = {"type": "water_pump", "action": action}
    if action == "start" and duration is not None:
        command["duration"] = duration
    return command


# --- persistence ---------------------------------------------------------


async def list_records(db: AsyncSession, *, limit: int = 50) -> list[dict[str, Any]]:
    """Return recent pump records, newest first."""
    stmt = select(WaterRecord).order_by(WaterRecord.started_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return [serialize_record(row) for row in result.scalars().all()]


async def list_records_paged(
    db: AsyncSession, *, page: int = 1, page_size: int = 20, max_pages: int = 99
) -> dict[str, Any]:
    """Return one page of pump records, newest first (for the paged table)."""
    page_size = max(1, min(100, page_size))
    total = (await db.execute(select(func.count()).select_from(WaterRecord))).scalar_one()
    pages = min(max_pages, max(1, (total + page_size - 1) // page_size))
    page = max(1, min(page, pages))
    result = await db.execute(
        select(WaterRecord)
        .order_by(WaterRecord.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [serialize_record(row) for row in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages}


async def usage_series(
    db: AsyncSession, *, granularity: str = "day", buckets: int | None = None
) -> list[dict[str, Any]]:
    """Aggregate dispensed water into fixed time buckets for the usage chart.

    ``granularity='hour'`` → last 24 hours; ``'day'`` → last ``buckets`` days
    (default 7). Returns continuous buckets (zero-filled) oldest→newest.
    """
    now = datetime.now()
    if granularity == "hour":
        count = buckets or 24
        start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=count - 1)
        keys = [start + timedelta(hours=i) for i in range(count)]

        def bucket_of(dt: datetime) -> datetime:
            return dt.replace(minute=0, second=0, microsecond=0)

        def label_of(dt: datetime) -> str:
            return dt.strftime("%H:00")
    else:
        count = buckets or 7
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=count - 1)
        keys = [start + timedelta(days=i) for i in range(count)]

        def bucket_of(dt: datetime) -> datetime:
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)

        def label_of(dt: datetime) -> str:
            return dt.strftime("%m-%d")

    agg: dict[datetime, dict[str, int]] = {k: {"volume_ml": 0, "count": 0} for k in keys}
    rows = (
        await db.execute(select(WaterRecord).where(WaterRecord.started_at >= start))
    ).scalars().all()
    for row in rows:
        if not row.started_at:
            continue
        key = bucket_of(row.started_at)
        if key in agg:
            agg[key]["volume_ml"] += estimate_volume_ml(row.duration_seconds)
            agg[key]["count"] += 1
    return [
        {"label": label_of(k), "volume_ml": agg[k]["volume_ml"], "count": agg[k]["count"]}
        for k in keys
    ]


async def create_pump_record(
    db: AsyncSession,
    *,
    device_id: str,
    duration_seconds: float,
    trigger_type: str = "manual",
) -> dict[str, Any]:
    """Record a pump activation that runs for ``duration_seconds``."""
    started_at = datetime.now()
    record = WaterRecord(
        device_id=device_id or "unknown-device",
        trigger_type=trigger_type,
        duration_seconds=duration_seconds,
        started_at=started_at,
        ended_at=started_at + timedelta(seconds=duration_seconds),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    logger.info("Water pump record created: device=%s duration=%ss", record.device_id, duration_seconds)
    return serialize_record(record)


async def stop_active_pump(db: AsyncSession) -> dict[str, Any] | None:
    """Clamp the most recent still-running pump record to now; return it or None."""
    now = datetime.now()
    stmt = (
        select(WaterRecord)
        .where(WaterRecord.ended_at > now)
        .order_by(WaterRecord.started_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    record = result.scalars().first()
    if record is None:
        return None

    record.ended_at = now
    record.duration_seconds = max(0, (now - record.started_at).total_seconds())
    await db.commit()
    await db.refresh(record)
    logger.info("Water pump stopped early: record=%s", record.id)
    return serialize_record(record)


async def list_schedules(db: AsyncSession) -> list[dict[str, Any]]:
    """Return all water schedules, newest first (so a new plan shows on top)."""
    stmt = select(WaterSchedule).order_by(WaterSchedule.id.desc())
    result = await db.execute(stmt)
    return [serialize_schedule(row) for row in result.scalars().all()]


async def create_schedule(
    db: AsyncSession,
    *,
    label: str,
    time: str,
    duration_seconds: float,
    enabled: bool = True,
) -> dict[str, Any]:
    """Create a new water schedule."""
    schedule = WaterSchedule(
        label=label or "未命名计划",
        time=time,
        duration_seconds=duration_seconds,
        enabled=enabled,
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return serialize_schedule(schedule)


async def update_schedule(
    db: AsyncSession, schedule_id: int, fields: dict[str, Any]
) -> dict[str, Any] | None:
    """Apply a partial update to a schedule; return it, or None if not found."""
    schedule = await db.get(WaterSchedule, schedule_id)
    if schedule is None:
        return None

    for key in ("label", "time", "duration_seconds", "enabled"):
        if key in fields and fields[key] is not None:
            setattr(schedule, key, fields[key])
    await db.commit()
    await db.refresh(schedule)
    return serialize_schedule(schedule)


async def delete_schedule(db: AsyncSession, schedule_id: int) -> bool:
    """Delete a schedule; return True if a row was removed."""
    schedule = await db.get(WaterSchedule, schedule_id)
    if schedule is None:
        return False
    await db.execute(delete(WaterSchedule).where(WaterSchedule.id == schedule_id))
    await db.commit()
    return True


def _water_subset(full: dict[str, Any]) -> dict[str, Any]:
    """Keep only the water-linkage keys from the full app settings."""
    return {"autoOnMeow": full["autoOnMeow"], "delaySeconds": full["delaySeconds"]}


async def get_settings(db: AsyncSession) -> dict[str, Any]:
    """Return the water-linkage subset of the shared app settings."""
    return _water_subset(await settings_service.get_settings(db))


async def save_settings(
    db: AsyncSession,
    *,
    auto_on_meow: bool | None = None,
    delay_seconds: int | None = None,
) -> dict[str, Any]:
    """Update the water-linkage settings within the shared app settings."""
    payload = {"autoOnMeow": auto_on_meow, "delaySeconds": delay_seconds}
    return _water_subset(await settings_service.save_settings(db, payload))
