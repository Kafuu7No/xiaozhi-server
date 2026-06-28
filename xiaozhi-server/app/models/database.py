"""Database models for persistent storage."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class SensorRecord(Base):
    """Temperature and humidity sensor readings reported by the device."""

    __tablename__ = "sensor_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(20), index=True)
    temperature: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20), default="device")
    sensor_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sensor_error: Mapped[str | None] = mapped_column(String(80), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MeowEvent(Base):
    """Cat-sound detection events reported by the device."""

    __tablename__ = "meow_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(20), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    is_cat: Mapped[bool] = mapped_column(Boolean, default=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WaterRecord(Base):
    """Water pump activation records."""

    __tablename__ = "water_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(20), index=True)
    trigger_type: Mapped[str] = mapped_column(String(20))
    duration_seconds: Mapped[float] = mapped_column(Float)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class WaterSchedule(Base):
    """Scheduled (timed) water-pump activations."""

    __tablename__ = "water_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(60))
    time: Mapped[str] = mapped_column(String(5))  # 'HH:MM'
    duration_seconds: Mapped[float] = mapped_column(Float)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AppSetting(Base):
    """Singleton row (id=1) holding user-adjustable app settings:
    detection thresholds and the cat-meow water linkage."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meow_threshold: Mapped[float] = mapped_column(Float, default=0.6)
    meow_min_confidence: Mapped[float] = mapped_column(Float, default=0.4)
    temp_max: Mapped[float] = mapped_column(Float, default=35.0)
    humid_min: Mapped[float] = mapped_column(Float, default=30.0)
    humid_max: Mapped[float] = mapped_column(Float, default=80.0)
    auto_on_meow: Mapped[bool] = mapped_column(Boolean, default=False)
    delay_seconds: Mapped[int] = mapped_column(Integer, default=5)


class CameraPhoto(Base):
    """Still photos captured by the device camera and uploaded to the server."""

    __tablename__ = "camera_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(20), index=True)
    filename: Mapped[str] = mapped_column(String(120))
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ConversationLog(Base):
    """Conversation history for STT and TTS text."""

    __tablename__ = "conversation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(20), index=True)
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    emotion: Mapped[str] = mapped_column(String(20), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
