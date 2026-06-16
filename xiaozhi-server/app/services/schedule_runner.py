"""Background runner that fires timed water-pump schedules.

Schedules (``WaterSchedule``) were previously stored but never executed — there
was no scheduler, so a plan set for e.g. 20:46 never ran. This task wakes every
~20s, and when the current HH:MM matches an enabled schedule it dispatches the
pump (via the UDP hardware bridge) and records it, de-duplicating per minute.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime

from sqlalchemy import select

from ..core.database import async_session
from ..models.database import WaterSchedule
from . import peer_config_service, retention, water_service
from .udp_hardware_bridge import DEVICE_ID, udp_hardware_bridge

logger = logging.getLogger("xz.schedule")

CHECK_INTERVAL_S = 20
PEER_CONFIG_INTERVAL_S = 30
PRUNE_INTERVAL_S = 3600  # 每小时清理一次过期数据


class ScheduleRunner:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._fired: set[str] = set()  # keys "id@YYYY-MM-DD HH:MM" already run
        self._last_prune = 0.0
        self._last_peer_push = 0.0

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())
            logger.info("Water schedule runner started")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await self._tick()
                await self._maybe_prune()
                await self._maybe_push_peer_config()
            except Exception:  # noqa: BLE001
                logger.exception("Schedule tick failed")
            await asyncio.sleep(CHECK_INTERVAL_S)

    async def _maybe_prune(self) -> None:
        now = time.monotonic()
        if now - self._last_prune < PRUNE_INTERVAL_S:
            return
        self._last_prune = now
        async with async_session() as db:
            await retention.prune_old(db)

    async def _maybe_push_peer_config(self) -> None:
        now = time.monotonic()
        if now - self._last_peer_push < PEER_CONFIG_INTERVAL_S:
            return
        self._last_peer_push = now
        async with async_session() as db:
            await peer_config_service.push_peer_config(db)

    async def _tick(self) -> None:
        now = datetime.now()
        hhmm = now.strftime("%H:%M")
        day = now.strftime("%Y-%m-%d")

        async with async_session() as db:
            result = await db.execute(
                select(WaterSchedule).where(WaterSchedule.enabled.is_(True))
            )
            for sched in result.scalars().all():
                if (sched.time or "").strip() != hhmm:
                    continue
                key = f"{sched.id}@{day} {hhmm}"
                if key in self._fired:
                    continue
                self._fired.add(key)

                duration = float(sched.duration_seconds or 0)
                sent = udp_hardware_bridge.send_pump_start(duration)
                await water_service.create_pump_record(
                    db,
                    device_id=DEVICE_ID,
                    duration_seconds=duration,
                    trigger_type="schedule",
                )
                logger.info(
                    "Schedule '%s' fired at %s: pump %ss (sent=%s)",
                    sched.label,
                    hhmm,
                    duration,
                    sent,
                )

        # Keep the de-dup set from growing without bound.
        if len(self._fired) > 2000:
            self._fired.clear()


schedule_runner = ScheduleRunner()
