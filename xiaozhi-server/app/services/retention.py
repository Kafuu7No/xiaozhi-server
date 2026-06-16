"""Data retention: delete time-series rows older than a cutoff.

Even with per-minute throttling the DB would grow forever, so we keep only the
last few days of sensor / water / meow rows. Photos are files on disk and are
managed separately (manual delete in the gallery).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import MeowEvent, SensorRecord, WaterRecord

logger = logging.getLogger("xz.retention")

RETENTION_DAYS = 3


async def prune_old(db: AsyncSession, *, days: int = RETENTION_DAYS) -> dict[str, Any]:
    """Delete sensor/water/meow rows older than ``days``; return per-table counts."""
    cutoff = datetime.now() - timedelta(days=days)
    deleted: dict[str, int] = {}
    for model, column in (
        (SensorRecord, SensorRecord.recorded_at),
        (WaterRecord, WaterRecord.started_at),
        (MeowEvent, MeowEvent.recorded_at),
    ):
        result = await db.execute(delete(model).where(column < cutoff))
        deleted[model.__name__] = int(result.rowcount or 0)
    await db.commit()
    total = sum(deleted.values())
    if total:
        logger.info("Retention pruned %d rows older than %dd: %s", total, days, deleted)
    return deleted
