"""Channel service: registration and lookups."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Channel
from app.models.channel import ChannelRole
from app.schemas.channel import ChannelCreate


async def add_channel(
    session: AsyncSession,
    user_id: int,
    data: ChannelCreate,
) -> Channel:
    """Register a new channel for ``user_id``.

    Re-adding a channel the user already registered (same platform + id)
    returns the existing row instead of creating a duplicate — duplicates
    would show up as repeated buttons in the manager bot pickers.  The role
    of an existing channel is never changed implicitly (use ``/setsource``).
    """
    existing = await find_by_platform_id(
        session, data.platform, data.platform_channel_id
    )
    if existing is not None and existing.user_id == user_id:
        if data.title and existing.title != data.title:
            existing.title = data.title
            await session.commit()
            await session.refresh(existing)
        return existing

    channel = Channel(
        user_id=user_id,
        platform=data.platform,
        platform_channel_id=data.platform_channel_id,
        title=data.title,
        role=data.role,
        is_active=data.is_active,
    )
    session.add(channel)
    await session.commit()
    await session.refresh(channel)
    return channel


async def list_channels(session: AsyncSession, user_id: int) -> list[Channel]:
    """List all channels owned by ``user_id``."""
    stmt = select(Channel).where(Channel.user_id == user_id).order_by(Channel.id)
    return list((await session.execute(stmt)).scalars().all())


async def get_channel(
    session: AsyncSession,
    channel_id: int,
    user_id: int | None = None,
) -> Channel | None:
    """Return a channel by id, optionally scoped to a user."""
    stmt = select(Channel).where(Channel.id == channel_id)
    if user_id is not None:
        stmt = stmt.where(Channel.user_id == user_id)
    return (await session.execute(stmt)).scalars().first()


async def find_by_platform_id(
    session: AsyncSession,
    platform: str,
    platform_channel_id: str,
    role: str | None = None,
) -> Channel | None:
    """Return a channel by its platform id and optional role."""
    stmt = select(Channel).where(
        Channel.platform == platform,
        Channel.platform_channel_id == str(platform_channel_id),
    )
    if role is not None:
        stmt = stmt.where(Channel.role == role)
    return (await session.execute(stmt)).scalars().first()


def _id_candidates(platform_channel_id: str, chat_username: str | None) -> set[str]:
    """Return every stored id that could identify this chat.

    A channel may have been registered as a numeric id or as an ``@username``,
    while an incoming update usually only carries the numeric id (plus, on some
    platforms, the username).  Matching against all candidates avoids silently
    dropping messages when the two forms differ.
    """
    candidates = {str(platform_channel_id)}
    if chat_username:
        username = str(chat_username).lstrip("@")
        candidates.add("@" + username)
        candidates.add(username)
    return candidates


async def find_source_channel(
    session: AsyncSession,
    platform: str,
    platform_channel_id: str,
    chat_username: str | None = None,
) -> Channel | None:
    """Return an active *source* channel for ``platform`` and channel id.

    ``platform_channel_id`` may be a numeric id or an ``@username``; when the
    incoming update also carries a ``chat_username`` the lookup matches either
    form.
    """
    stmt = select(Channel).where(
        Channel.platform == platform,
        Channel.platform_channel_id.in_(
            _id_candidates(platform_channel_id, chat_username)
        ),
        Channel.role == ChannelRole.SOURCE,
        Channel.is_active.is_(True),
    )
    return (await session.execute(stmt)).scalars().first()


async def set_active(
    session: AsyncSession,
    channel_id: int,
    active: bool,
) -> Channel | None:
    """Enable/disable a channel."""
    channel = await session.get(Channel, channel_id)
    if channel is None:
        return None
    channel.is_active = active
    await session.commit()
    return channel
