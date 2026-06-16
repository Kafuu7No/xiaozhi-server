"""Sensor persistence, serialization, and broadcast helpers."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models.database import SensorRecord
from . import settings_service
from .broadcast import broadcast

# Persist at most one sensor record per device every N seconds. The board pushes
# readings far more often than that; without throttling the DB grows unbounded.
# Live dashboard updates are still broadcast every time — only DB writes throttle.
MIN_PERSIST_INTERVAL_S = 60.0  # 落库间隔：每设备最快 1 分钟一条
_last_persist_at: dict[str, float] = {}

# 数据保留天数：超过的记录定期清理，防止数据库无限增长
RETENTION_DAYS = 3

logger = logging.getLogger("xz.sensor")


def _server_ts(recorded_at: datetime) -> int:
    return int(recorded_at.timestamp() * 1000)


def build_alerts(
    temp_c: float,
    humi_rh: float,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Evaluate sensor alerts. ``thresholds`` (keys ``temp_max``/``humid_min``/
    ``humid_max``) overrides the static config defaults when provided."""
    if thresholds is None:
        settings = get_settings()
        thresholds = {
            "temp_max": settings.sensor_temp_max,
            "humid_min": settings.sensor_humid_min,
            "humid_max": settings.sensor_humid_max,
        }
    return {
        "temp_high": temp_c > thresholds["temp_max"],
        "humi_low": humi_rh < thresholds["humid_min"],
        "humi_high": humi_rh > thresholds["humid_max"],
        "thresholds": {
            "temp_max": thresholds["temp_max"],
            "humi_min": thresholds["humid_min"],
            "humi_max": thresholds["humid_max"],
        },
    }


def serialize_record(
    record: SensorRecord,
    *,
    device_ts: int | None = None,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    alerts = build_alerts(record.temperature, record.humidity, thresholds)
    payload = {
        "id": record.id,
        "device_id": record.device_id,
        "temp_c": record.temperature,
        "humi_rh": record.humidity,
        "source": record.source or "device",
        "sensor_ok": record.sensor_ok,
        "sensor_error": record.sensor_error,
        "ts": _server_ts(record.recorded_at),
        "recorded_at": record.recorded_at.isoformat(),
        "alerts": alerts,
        "has_alert": any((alerts["temp_high"], alerts["humi_low"], alerts["humi_high"])),
    }
    if device_ts is not None:
        payload["device_ts"] = device_ts
    return payload


async def save_record(
    db: AsyncSession,
    *,
    device_id: str,
    temp_c: float,
    humi_rh: float,
    ts: int | None = None,
    recorded_at: datetime | None = None,
    source: str = "device",
    sensor_ok: bool | None = None,
    sensor_error: str | None = None,
) -> dict[str, Any]:
    """Broadcast one sensor sample live; persist at most once per 10s per device."""
    device_id = device_id or "unknown-device"
    recorded_at = recorded_at or datetime.now()
    thresholds = await settings_service.get_thresholds(db)

    now = time.monotonic()
    persist = (now - _last_persist_at.get(device_id, 0.0)) >= MIN_PERSIST_INTERVAL_S

    if persist:
        _last_persist_at[device_id] = now
        record = SensorRecord(
            device_id=device_id,
            temperature=float(temp_c),
            humidity=float(humi_rh),
            source=source,
            sensor_ok=sensor_ok,
            sensor_error=sensor_error,
            recorded_at=recorded_at,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        payload = serialize_record(record, device_ts=ts, thresholds=thresholds)
        logger.info(
            "Sensor record stored from %s: device=%s temp=%.2f humi=%.2f",
            source,
            device_id,
            record.temperature,
            record.humidity,
        )
    else:
        # Throttled: build a transient payload for the live dashboard, no DB row.
        alerts = build_alerts(float(temp_c), float(humi_rh), thresholds)
        payload = {
            "id": None,
            "device_id": device_id,
            "temp_c": float(temp_c),
            "humi_rh": float(humi_rh),
            "source": source or "device",
            "sensor_ok": sensor_ok,
            "sensor_error": sensor_error,
            "ts": _server_ts(recorded_at),
            "recorded_at": recorded_at.isoformat(),
            "alerts": alerts,
            "has_alert": any((alerts["temp_high"], alerts["humi_low"], alerts["humi_high"])),
        }
        if ts is not None:
            payload["device_ts"] = ts

    await broadcast("sensor_update", payload)
    if payload["has_alert"]:
        await broadcast("sensor_alert", payload)
    return payload


async def get_latest(db: AsyncSession) -> SensorRecord | None:
    result = await db.execute(
        select(SensorRecord).order_by(SensorRecord.recorded_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def get_history(db: AsyncSession, hours: int) -> list[dict[str, Any]]:
    since = datetime.now() - timedelta(hours=hours)
    result = await db.execute(
        select(SensorRecord)
        .where(SensorRecord.recorded_at >= since)
        .order_by(SensorRecord.recorded_at.asc())
    )
    thresholds = await settings_service.get_thresholds(db)
    return [serialize_record(row, thresholds=thresholds) for row in result.scalars().all()]


async def list_records_paged(
    db: AsyncSession, *, page: int = 1, page_size: int = 20, max_pages: int = 99
) -> dict[str, Any]:
    """Return one page of sensor records, newest first (for the paged table)."""
    page_size = max(1, min(100, page_size))
    total = (await db.execute(select(func.count()).select_from(SensorRecord))).scalar_one()
    pages = min(max_pages, max(1, (total + page_size - 1) // page_size))
    page = max(1, min(page, pages))
    thresholds = await settings_service.get_thresholds(db)
    result = await db.execute(
        select(SensorRecord)
        .order_by(SensorRecord.recorded_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [serialize_record(row, thresholds=thresholds) for row in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages}


async def get_stats(db: AsyncSession, hours: int) -> dict[str, Any]:
    since = datetime.now() - timedelta(hours=hours)
    result = await db.execute(
        select(
            func.count(SensorRecord.id),
            func.min(SensorRecord.temperature),
            func.max(SensorRecord.temperature),
            func.avg(SensorRecord.temperature),
            func.min(SensorRecord.humidity),
            func.max(SensorRecord.humidity),
            func.avg(SensorRecord.humidity),
        ).where(SensorRecord.recorded_at >= since)
    )
    sample_count, temp_min, temp_max, temp_avg, humi_min, humi_max, humi_avg = result.one()

    return {
        "hours": hours,
        "sample_count": sample_count or 0,
        "temp_c": {
            "min": round(temp_min, 2) if temp_min is not None else None,
            "max": round(temp_max, 2) if temp_max is not None else None,
            "avg": round(temp_avg, 2) if temp_avg is not None else None,
        },
        "humi_rh": {
            "min": round(humi_min, 2) if humi_min is not None else None,
            "max": round(humi_max, 2) if humi_max is not None else None,
            "avg": round(humi_avg, 2) if humi_avg is not None else None,
        },
    }
