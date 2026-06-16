"""Sensor REST API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services import sensor_service, settings_service

router = APIRouter()


@router.get("/sensor/latest")
async def get_sensor_latest(db: AsyncSession = Depends(get_db)) -> dict:
    record = await sensor_service.get_latest(db)
    if record is None:
        raise HTTPException(status_code=404, detail="No sensor data yet")
    thresholds = await settings_service.get_thresholds(db)
    return sensor_service.serialize_record(record, thresholds=thresholds)


@router.get("/sensor/history")
async def get_sensor_history(
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await sensor_service.get_history(db, hours)


@router.get("/sensor/records")
async def get_sensor_records(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Paged sensor records (newest first), max 99 pages."""
    return await sensor_service.list_records_paged(db, page=page, page_size=page_size)


@router.get("/sensor/stats")
async def get_sensor_stats(
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await sensor_service.get_stats(db, hours)


@router.get("/sensor/thresholds")
async def get_sensor_thresholds(db: AsyncSession = Depends(get_db)) -> dict:
    thresholds = await settings_service.get_thresholds(db)
    return {
        "temp_max": thresholds["temp_max"],
        "humi_min": thresholds["humid_min"],
        "humi_max": thresholds["humid_max"],
    }
