"""Pytest configuration for isolated database-backed tests."""

import os

# Must be set before any app.* imports so app.core.database points to the test DB.
os.environ["XZ_DATABASE_URL"] = "sqlite+aiosqlite:///./test_xiaozhi.db"

import pytest_asyncio

collect_ignore = ["test_handshake.py", "test_ws_handshake.py"]


@pytest_asyncio.fixture
async def db_ready():
    """Recreate all database tables before each test that needs persistence."""
    from app.core.database import Base, engine
    import app.models.database  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
