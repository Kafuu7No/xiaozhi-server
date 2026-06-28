"""Meow-event parsing, persistence, serialization, and broadcast helpers."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import MeowEvent
from .broadcast import broadcast

logger = logging.getLogger("xz.meow")

MIN_CONFIDENCE = 0.4


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "cat"}:
            return True
        if lowered in {"false", "0", "no", "noise"}:
            return False
    return None


def parse_meow_payload(
    message: dict[str, Any], threshold: float = 0.6
) -> dict[str, Any] | None:
    """Extract meow event fields from the device payload.

    ``threshold`` is the cloud-side score above which an event is classified as
    a cat. The device may still report its local judgement, but cloud views use
    this value so dashboard settings have a real effect.
    """
    score = _to_float(message.get("score"))
    if score is None:
        score = _to_float(message.get("confidence"))

    is_cat = _to_bool(message.get("is_cat"))
    if is_cat is None:
        is_cat = _to_bool(message.get("confirmed_detected"))

    ts = message.get("ts")
    if score is not None:
        return {
            "score": score,
            "device_is_cat": is_cat,
            "is_cat": score >= threshold,
            "ts": int(ts) if isinstance(ts, (int, float)) and not isinstance(ts, bool) else None,
        }

    nested = message.get("data")
    if isinstance(nested, dict):
        return parse_meow_payload(nested, threshold)
    return None


def serialize_event(event: MeowEvent, *, device_ts: int | None = None) -> dict[str, Any]:
    payload = {
        "id": event.id,
        "device_id": event.device_id,
        "score": event.confidence,
        "is_cat": event.is_cat,
        "ts": int(event.recorded_at.timestamp() * 1000),
        "recorded_at": event.recorded_at.isoformat(),
    }
    if device_ts is not None:
        payload["device_ts"] = device_ts
    return payload


async def save_event(
    db: AsyncSession,
    *,
    device_id: str,
    score: float,
    is_cat: bool,
    min_confidence: float = MIN_CONFIDENCE,
    ts: int | None = None,
    recorded_at: datetime | None = None,
    source: str = "device",
) -> dict[str, Any]:
    if score < min_confidence:
        logger.debug(
            "Meow event dropped from %s: device=%s score=%.3f below minimum %.2f",
            source,
            device_id,
            score,
            min_confidence,
        )
        return {
            "status": "dropped",
            "reason": "below_min_confidence",
            "min_confidence": min_confidence,
            "score": float(score),
            "is_cat": bool(is_cat),
        }

    event = MeowEvent(
        device_id=device_id or "unknown-device",
        confidence=float(score),
        is_cat=bool(is_cat),
        recorded_at=recorded_at or datetime.now(),
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    payload = serialize_event(event, device_ts=ts)
    payload["source"] = source
    payload["min_confidence"] = min_confidence
    await broadcast("meow_event", payload)

    logger.info(
        "Meow event stored from %s: device=%s score=%.3f is_cat=%s",
        source,
        event.device_id,
        event.confidence,
        event.is_cat,
    )
    return payload


async def get_events(
    db: AsyncSession,
    *,
    hours: int,
    is_cat: bool | None = None,
    min_confidence: float = MIN_CONFIDENCE,
) -> list[dict[str, Any]]:
    lower_bound = datetime.now() - timedelta(hours=hours)
    stmt = (
        select(MeowEvent)
        .where(MeowEvent.recorded_at >= lower_bound)
        .where(MeowEvent.confidence >= min_confidence)
        .order_by(MeowEvent.recorded_at.desc())
    )
    if is_cat is not None:
        stmt = stmt.where(MeowEvent.is_cat == is_cat)
    result = await db.execute(stmt)
    return [serialize_event(row) for row in result.scalars().all()]


async def get_stats(db: AsyncSession, min_confidence: float = MIN_CONFIDENCE) -> dict[str, Any]:
    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    async def _count(*, is_cat: bool | None = None) -> int:
        stmt = (
            select(func.count())
            .select_from(MeowEvent)
            .where(MeowEvent.recorded_at >= start_of_day)
            .where(MeowEvent.confidence >= min_confidence)
        )
        if is_cat is not None:
            stmt = stmt.where(MeowEvent.is_cat == is_cat)
        result = await db.execute(stmt)
        return result.scalar_one()

    today_total = await _count()
    today_cat = await _count(is_cat=True)
    today_noise = await _count(is_cat=False)
    return {
        "today_total": today_total,
        "today_cat": today_cat,
        "today_noise": today_noise,
        "min_confidence": min_confidence,
    }
