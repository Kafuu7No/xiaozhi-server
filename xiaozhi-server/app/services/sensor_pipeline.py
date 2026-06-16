"""Sensor ingestion, persistence, and alert evaluation helpers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models.database import SensorRecord
from .broadcast import broadcast

logger = logging.getLogger("xz.sensor")

_TEMP_KEYS = ("temperature", "temp", "temp_c", "temperature_c")
_HUMIDITY_KEYS = (
    "humidity",
    "humid",
    "humi_rh",
    "humid_rh",
    "humidity_percent",
    "relative_humidity",
)
_TIMESTAMP_KEYS = ("timestamp", "recorded_at", "ts", "time")
_SENSOR_DEVICE_NAMES = {
    "aht20",
    "sensor",
    "temphumidity",
    "temperaturehumidity",
    "climate",
    "environment",
}


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pick_number(payload: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = _to_float(payload.get(key))
        if value is not None:
            return value
    return None


def _to_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        timestamp = float(value)
        if timestamp > 1_000_000_000_000:
            timestamp /= 1000
        try:
            return datetime.fromtimestamp(timestamp, timezone.utc).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        numeric = _to_float(text)
        if numeric is not None:
            return _to_datetime(numeric)
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    return None


def _looks_like_sensor_name(name: str) -> bool:
    normalized = "".join(ch for ch in name.lower() if ch.isalnum())
    return normalized in _SENSOR_DEVICE_NAMES


def parse_sensor_payload(message: dict[str, Any]) -> dict[str, float] | None:
    """Extract temperature and humidity from multiple possible device message shapes."""
    direct = {
        "temperature": _pick_number(message, _TEMP_KEYS),
        "humidity": _pick_number(message, _HUMIDITY_KEYS),
    }
    if None not in direct.values():
        return direct

    for key in ("payload", "params", "result", "state", "data", "reading"):
        nested_obj = message.get(key)
        if isinstance(nested_obj, dict):
            nested = parse_sensor_payload(nested_obj)
            if nested:
                return nested

    states = message.get("states")
    if isinstance(states, list):
        for item in states:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", ""))
            if not name or not _looks_like_sensor_name(name):
                continue
            state = item.get("state")
            if not isinstance(state, dict):
                continue
            nested = {
                "temperature": _pick_number(state, _TEMP_KEYS),
                "humidity": _pick_number(state, _HUMIDITY_KEYS),
            }
            if None not in nested.values():
                return nested

    return None


def parse_sensor_recorded_at(message: dict[str, Any]) -> datetime | None:
    for key in _TIMESTAMP_KEYS:
        parsed = _to_datetime(message.get(key))
        if parsed is not None:
            return parsed

    for key in ("payload", "params", "result", "state", "data", "reading"):
        nested_obj = message.get(key)
        if isinstance(nested_obj, dict):
            nested = parse_sensor_recorded_at(nested_obj)
            if nested is not None:
                return nested

    return None


def build_sensor_alerts(temperature: float, humidity: float) -> dict[str, Any]:
    settings = get_settings()
    return {
        "temperature_high": temperature > settings.sensor_temp_max,
        "humidity_low": humidity < settings.sensor_humid_min,
        "humidity_high": humidity > settings.sensor_humid_max,
        "thresholds": {
            "temp_max": settings.sensor_temp_max,
            "humid_min": settings.sensor_humid_min,
            "humid_max": settings.sensor_humid_max,
        },
    }


def build_sensor_snapshot(record: SensorRecord) -> dict[str, Any]:
    alerts = build_sensor_alerts(record.temperature, record.humidity)
    return {
        "device_id": record.device_id,
        "temperature": record.temperature,
        "humidity": record.humidity,
        "recorded_at": record.recorded_at.isoformat(),
        "alerts": alerts,
        "has_alert": any(
            (
                alerts["temperature_high"],
                alerts["humidity_low"],
                alerts["humidity_high"],
            )
        ),
    }


async def ingest_sensor_reading(
    db: AsyncSession,
    *,
    device_id: str,
    temperature: float,
    humidity: float,
    recorded_at: datetime | None = None,
    source: str = "device",
) -> dict[str, Any]:
    """Persist a sensor reading and push it to dashboard listeners."""
    timestamp = recorded_at or datetime.utcnow()
    record = SensorRecord(
        device_id=device_id or "unknown-device",
        temperature=temperature,
        humidity=humidity,
        recorded_at=timestamp,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    snapshot = build_sensor_snapshot(record)
    snapshot["source"] = source

    await broadcast("sensor_update", snapshot)
    if snapshot["has_alert"]:
        await broadcast("sensor_alert", snapshot)

    logger.info(
        "Sensor reading stored from %s: device=%s temp=%.1f humidity=%.1f",
        source,
        record.device_id,
        record.temperature,
        record.humidity,
    )
    return snapshot
