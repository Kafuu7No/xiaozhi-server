"""SQLite async database setup using SQLAlchemy 2.0."""

import os

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv("XZ_DATABASE_URL", "sqlite+aiosqlite:///./xiaozhi.db")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_sqlite_schema)


def _migrate_sqlite_schema(sync_conn):
    if not str(DATABASE_URL).startswith("sqlite"):
        return

    inspector = inspect(sync_conn)
    if "sensor_records" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("sensor_records")}
    migrations = {
        "source": "ALTER TABLE sensor_records ADD COLUMN source VARCHAR(20) DEFAULT 'device'",
        "sensor_ok": "ALTER TABLE sensor_records ADD COLUMN sensor_ok BOOLEAN",
        "sensor_error": "ALTER TABLE sensor_records ADD COLUMN sensor_error VARCHAR(80)",
    }
    for column, statement in migrations.items():
        if column not in existing:
            sync_conn.execute(text(statement))


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
