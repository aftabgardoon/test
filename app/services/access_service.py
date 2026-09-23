"""Access control for the manager bot.

The manager UI is locked by default: a user must send the secret command
``/RSAsecret`` (see :data:`app.config.Settings.manager_access_secret`) before
any menu or reply is shown to them.  Granted users are persisted in the
``authorized_users`` table so the unlock survives restarts.

When ``manager_access_secret`` is empty the gate is disabled and everyone is
allowed — this keeps local development and the test-suite usable.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthorizedUser


async def is_authorized(
    session: AsyncSession,
    platform: str,
    platform_user_id: str,
) -> bool:
    """Return ``True`` when the user has already unlocked the manager bot."""
    stmt = select(AuthorizedUser.id).where(
        AuthorizedUser.platform == platform,
        AuthorizedUser.platform_user_id == str(platform_user_id),
    )
    return (await session.execute(stmt)).first() is not None


async def grant_access(
    session: AsyncSession,
    platform: str,
    platform_user_id: str,
) -> AuthorizedUser:
    """Authorize a user (idempotent) and return their row."""
    stmt = select(AuthorizedUser).where(
        AuthorizedUser.platform == platform,
        AuthorizedUser.platform_user_id == str(platform_user_id),
    )
    existing = (await session.execute(stmt)).scalars().first()
    if existing is not None:
        return existing

    row = AuthorizedUser(platform=platform, platform_user_id=str(platform_user_id))
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row
