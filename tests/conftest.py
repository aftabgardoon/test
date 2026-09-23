"""Shared pytest fixtures.

Configures a throwaway SQLite database and disables Redis so tests run
against the in-memory queue.
"""

from __future__ import annotations

import os
import tempfile

import pytest

# --- Configure environment BEFORE importing app modules ---
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp.name}"
os.environ["QUEUE_ENABLED"] = "false"
os.environ["FERNET_KEY"] = ""
os.environ["WEBHOOK_SECRET"] = "test-secret"
os.environ["POLLING_TIMEOUT"] = "15"
os.environ["POLLING_ENABLED"] = "false"
os.environ["BALE_BOT_TOKEN"] = ""
os.environ["RUBIKA_BOT_TOKEN"] = ""
os.environ["EITAA_BOT_TOKEN"] = ""
os.environ["MANAGER_BOT_TOKEN"] = ""
# Disable the /RSAsecret gate for the existing test-suite; the gate itself is
# covered by tests/test_access_gate.py which enables it explicitly.
os.environ["MANAGER_ACCESS_SECRET"] = ""


@pytest.fixture
async def _clean_database():
    """Drop and recreate all tables before each test."""
    from app.database import Base, dispose_engine, get_engine
    from app.services.cache_service import cache_service

    await dispose_engine()
    cache_service.clear()
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    cache_service.clear()
    await dispose_engine()


@pytest.fixture
async def db_session(_clean_database):
    """Yield a database session (with a freshly created schema)."""
    from app.database import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        yield session
