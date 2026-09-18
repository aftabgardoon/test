"""Async SQLAlchemy engine, session factory and helpers."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    """Return the (lazily created) async engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        kwargs: dict = {"echo": settings.debug, "future": True}
        if settings.database_url.startswith("postgresql"):
            kwargs.update(
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
        _engine = create_async_engine(settings.database_url, **kwargs)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the (lazily created) async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an :class:`AsyncSession`."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def init_db() -> None:
    """Create all tables if they do not exist (dev/test convenience).

    In production, prefer Alembic migrations.
    """
    from app import models  # noqa: F401  (ensures models are registered)

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    """Dispose the engine and clear cached factories."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
