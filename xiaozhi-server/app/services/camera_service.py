"""Camera photo helpers: filename generation, serialization, capture command."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import CameraPhoto

logger = logging.getLogger("xz.camera")

PHOTO_URL_PREFIX = "/photos"
PHOTOS_DIR = Path(__file__).resolve().parents[2] / "photos"
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9_-]")


def build_photo_filename(device_id: str, captured_at: datetime, micros: int | None = None) -> str:
    """Build a filesystem-safe, unique photo filename for an upload.

    Device ids may be MAC addresses (``aa:bb:cc:...``); ``:`` is illegal in
    Windows filenames, so every unsafe character is replaced with ``_``.
    """
    safe_device = _UNSAFE_CHARS.sub("_", device_id or "device")
    micros = captured_at.microsecond if micros is None else micros
    stamp = captured_at.strftime("%Y%m%d_%H%M%S")
    return f"{safe_device}_{stamp}_{micros:06d}.jpg"


def serialize_photo(photo: CameraPhoto | None) -> dict[str, Any] | None:
    """Serialize a photo record into the API response shape."""
    if photo is None:
        return None
    return {
        "id": photo.id,
        "device_id": photo.device_id,
        "filename": photo.filename,
        "url": f"{PHOTO_URL_PREFIX}/{photo.filename}",
        "captured_at": photo.captured_at.isoformat(),
    }


def build_capture_command() -> dict[str, Any]:
    """Build the WebSocket payload that tells the device to take a photo."""
    return {"type": "camera", "action": "capture"}


async def save_photo(
    db: AsyncSession,
    *,
    device_id: str,
    image_bytes: bytes,
    captured_at: datetime | None = None,
) -> dict[str, Any]:
    """Persist an uploaded photo to disk and record it in the database."""
    device_id = device_id or "unknown-device"
    captured_at = captured_at or datetime.now()
    filename = build_photo_filename(device_id, captured_at)

    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    (PHOTOS_DIR / filename).write_bytes(image_bytes)

    photo = CameraPhoto(device_id=device_id, filename=filename, captured_at=captured_at)
    db.add(photo)
    await db.commit()
    await db.refresh(photo)

    logger.info("Camera photo stored: device=%s file=%s bytes=%d", device_id, filename, len(image_bytes))
    return serialize_photo(photo)  # type: ignore[return-value]


async def get_latest_photo(db: AsyncSession) -> dict[str, Any] | None:
    """Return the most recently captured photo, or None if none exist."""
    stmt = select(CameraPhoto).order_by(CameraPhoto.captured_at.desc()).limit(1)
    result = await db.execute(stmt)
    return serialize_photo(result.scalars().first())


async def list_photos(db: AsyncSession, *, limit: int = 50) -> list[dict[str, Any]]:
    """Return recent photos, newest first, for the history gallery."""
    stmt = select(CameraPhoto).order_by(CameraPhoto.captured_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return [serialize_photo(row) for row in result.scalars().all()]


async def list_photos_paged(
    db: AsyncSession, *, page: int = 1, page_size: int = 15, max_pages: int = 99
) -> dict[str, Any]:
    """Return one page of photos, newest first, for the paged gallery."""
    page_size = max(1, min(60, page_size))
    total = (await db.execute(select(func.count()).select_from(CameraPhoto))).scalar_one()
    pages = min(max_pages, max(1, (total + page_size - 1) // page_size))
    page = max(1, min(page, pages))
    result = await db.execute(
        select(CameraPhoto)
        .order_by(CameraPhoto.captured_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    photos = [serialize_photo(row) for row in result.scalars().all()]
    return {"photos": photos, "total": total, "page": page, "page_size": page_size, "pages": pages}


async def delete_photo(db: AsyncSession, photo_id: int) -> bool:
    """Delete a photo's DB row and its file on disk. Returns True if removed."""
    photo = await db.get(CameraPhoto, photo_id)
    if photo is None:
        return False
    try:
        (PHOTOS_DIR / photo.filename).unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Could not delete photo file %s: %s", photo.filename, exc)
    await db.delete(photo)
    await db.commit()
    logger.info("Camera photo deleted: id=%s file=%s", photo_id, photo.filename)
    return True
