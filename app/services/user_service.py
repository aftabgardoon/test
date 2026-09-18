"""User service: registration and lookups."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.user import UserCreate


async def get_or_create_user(
    session: AsyncSession,
    platform: str,
    platform_user_id: str,
    username: str | None = None,
) -> User:
    """Return an existing user or create a new one."""
    stmt = select(User).where(
        User.platform == platform,
        User.platform_user_id == str(platform_user_id),
    )
    user = (await session.execute(stmt)).scalars().first()
    if user is not None:
        if username and user.username != username:
            user.username = username
            await session.commit()
        return user

    user = User(
        platform=platform,
        platform_user_id=str(platform_user_id),
        username=username,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def create_user(session: AsyncSession, data: UserCreate) -> User:
    """Create a user from a :class:`UserCreate` payload."""
    user = User(
        platform=data.platform,
        platform_user_id=data.platform_user_id,
        username=data.username,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    """Return a user by primary key."""
    return await session.get(User, user_id)
