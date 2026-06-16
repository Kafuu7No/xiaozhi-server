"""App settings service: detection thresholds + water linkage, stored as a
single row and exposed to the dashboard."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import AppSetting
from .meow_service import MIN_CONFIDENCE

logger = logging.getLogger("xz.settings")

# Maps API (camelCase) keys to AppSetting column names.
_FIELD_MAP = {
    "meowThreshold": "meow_threshold",
    "tempMax": "temp_max",
    "humidMin": "humid_min",
    "humidMax": "humid_max",
    "autoOnMeow": "auto_on_meow",
    "delaySeconds": "delay_seconds",
}


def serialize_settings(setting: AppSetting) -> dict[str, Any]:
    """Serialize a settings row using the camelCase keys the frontend expects."""
    return {
        "meowThreshold": setting.meow_threshold,
        "meowMinConfidence": MIN_CONFIDENCE,
        "tempMax": setting.temp_max,
        "humidMin": setting.humid_min,
        "humidMax": setting.humid_max,
        "autoOnMeow": setting.auto_on_meow,
        "delaySeconds": setting.delay_seconds,
    }


def to_db_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert a camelCase API payload to column updates, dropping unknown
    keys and keys whose value is None."""
    return {
        _FIELD_MAP[key]: value
        for key, value in payload.items()
        if key in _FIELD_MAP and value is not None
    }


# --- persistence ---------------------------------------------------------


async def get_or_create(db: AsyncSession) -> AppSetting:
    """Return the singleton settings row, creating it with defaults if absent."""
    setting = await db.get(AppSetting, 1)
    if setting is None:
        setting = AppSetting(id=1)
        db.add(setting)
        await db.commit()
        await db.refresh(setting)
    return setting


async def get_settings(db: AsyncSession) -> dict[str, Any]:
    """Return all app settings in API shape."""
    return serialize_settings(await get_or_create(db))


async def get_thresholds(db: AsyncSession) -> dict[str, float]:
    """Return the sensor alert thresholds (keys temp_max/humid_min/humid_max)."""
    setting = await get_or_create(db)
    return {
        "temp_max": setting.temp_max,
        "humid_min": setting.humid_min,
        "humid_max": setting.humid_max,
    }


async def get_meow_threshold(db: AsyncSession) -> float:
    """Return the cat-meow classification score threshold."""
    return (await get_or_create(db)).meow_threshold


async def save_settings(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    """Apply a partial (camelCase) update and return the stored settings."""
    setting = await get_or_create(db)
    for column, value in to_db_fields(payload).items():
        setattr(setting, column, value)
    await db.commit()
    await db.refresh(setting)
    logger.info("App settings updated: %s", to_db_fields(payload))
    return serialize_settings(setting)
