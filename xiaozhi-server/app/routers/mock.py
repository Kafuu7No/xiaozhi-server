"""Mock data endpoints for frontend development without a real device."""

import random

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services import settings_service
from ..services.meow_service import save_event
from ..services.sensor_service import save_record
from ..services.session_manager import session_manager

router = APIRouter(prefix="/api/mock")


@router.post("/sensor")
async def mock_sensor(db: AsyncSession = Depends(get_db)) -> dict:
    """Insert a simulated sensor reading and push it to dashboard clients."""
    sessions = list(session_manager._sessions.values())
    device_id = sessions[0][0].device_id if sessions else "mock-device"

    temperature = round(random.uniform(20.0, 30.0), 1)
    humidity = round(random.uniform(40.0, 80.0), 1)
    return await save_record(
        db,
        device_id=device_id,
        temp_c=temperature,
        humi_rh=humidity,
        source="mock",
    )


@router.post("/meow")
async def mock_meow(db: AsyncSession = Depends(get_db)) -> dict:
    """Insert a simulated meow event and push it to dashboard clients."""
    from datetime import datetime

    sessions = list(session_manager._sessions.values())
    device_id = sessions[0][0].device_id if sessions else "mock-device"

    confidence = round(random.uniform(0.5, 1.0), 2)
    threshold = await settings_service.get_meow_threshold(db)
    is_cat = confidence >= threshold
    recorded_at = datetime.utcnow()
    return await save_event(
        db,
        device_id=device_id,
        score=confidence,
        is_cat=is_cat,
        recorded_at=recorded_at,
        source="mock",
    )
