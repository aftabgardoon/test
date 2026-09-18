"""Token storage and resolution.

Bot tokens are stored encrypted in the ``bot_tokens`` table and decrypted on
demand. Resolution order for a ``(platform, owner_user_id)`` pair:

1. The most recent ``bot_tokens`` row for that platform/owner.
2. A fallback platform-level environment token (``*_BOT_TOKEN``).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import AdapterError
from app.config import get_settings
from app.models import BotToken
from app.utils.crypto import CryptoError, get_cipher


async def store_token(
    session: AsyncSession,
    platform: str,
    token: str,
    owner_user_id: int | None = None,
) -> BotToken:
    """Encrypt and persist a bot token, replacing any existing one."""
    cipher = get_cipher()
    encrypted = cipher.encrypt(token)

    stmt = select(BotToken).where(
        BotToken.platform == platform,
        BotToken.owner_user_id == owner_user_id,
    )
    existing = (await session.execute(stmt)).scalars().first()
    if existing is not None:
        existing.token = encrypted
    else:
        existing = BotToken(platform=platform, token=encrypted, owner_user_id=owner_user_id)
        session.add(existing)
    await session.commit()
    return existing


async def resolve_token(
    session: AsyncSession,
    platform: str,
    owner_user_id: int | None = None,
) -> str:
    """Return the plaintext token for ``platform`` / ``owner_user_id``.

    Raises:
        AdapterError: if no token is configured.
    """
    stmt = (
        select(BotToken)
        .where(BotToken.platform == platform, BotToken.owner_user_id == owner_user_id)
        .order_by(BotToken.id.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).scalars().first()
    if row is not None:
        try:
            return get_cipher().decrypt(row.token)
        except CryptoError as exc:
            raise AdapterError(f"Failed to decrypt token for {platform}") from exc

    settings = get_settings()
    env_token = _platform_env_token(platform, settings)
    if env_token:
        return env_token

    raise AdapterError(f"No bot token configured for platform {platform!r}")


def _platform_env_token(platform: str, settings) -> str:
    """Return a platform-level token from environment settings, if any."""
    if platform == "bale":
        return settings.bale_bot_token or settings.manager_bot_token
    if platform == "rubika":
        return settings.rubika_bot_token
    if platform == "eitaa":
        return settings.eitaa_bot_token
    return ""
