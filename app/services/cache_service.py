"""In-memory cache for frequently-read data (channels, links, tokens).

Avoids a database round-trip for every incoming message. The cache is a
singleton (:data:`cache_service`) and is warmed up at startup, invalidated
after user mutations (add channel, create link, toggle link, store token).
"""

from __future__ import annotations

import asyncio

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import BotToken, Channel, SyncLink
from app.models.channel import ChannelRole
from app.services import channel_service, token_service


class CacheService:
    """Thread-safe (async) cache over channels, sync links and bot tokens."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._source_channels: dict[tuple[str, str], Channel] = {}
        self._links_by_source: dict[int, list[SyncLink]] = {}
        self._bot_tokens: dict[tuple[str, int], str] = {}

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    async def get_source_channel(
        self,
        session: AsyncSession,
        platform: str,
        platform_channel_id: str,
        chat_username: str | None = None,
    ) -> Channel | None:
        """Return the active source channel for ``platform`` / channel id.

        The channel may have been registered as an ``@username`` while the
        update carries the numeric id (or vice-versa); every candidate key is
        checked before falling back to a database lookup.
        """
        keys = self._source_keys(platform, platform_channel_id, chat_username)
        for key in keys:
            if key in self._source_channels:
                return self._source_channels[key]
        async with self._lock:
            for key in keys:
                if key in self._source_channels:
                    return self._source_channels[key]
            channel = await channel_service.find_source_channel(
                session, platform, platform_channel_id, chat_username
            )
            if channel is not None:
                for key in keys:
                    self._source_channels[key] = channel
            return channel

    @staticmethod
    def _source_keys(
        platform: str, platform_channel_id: str, chat_username: str | None
    ) -> list[tuple[str, str]]:
        """Candidate cache keys for a source channel (id and/or username)."""
        keys = [(platform, str(platform_channel_id))]
        if chat_username:
            username = str(chat_username).lstrip("@")
            for candidate in ("@" + username, username):
                key = (platform, candidate)
                if key not in keys:
                    keys.append(key)
        return keys

    async def get_active_links_by_source(
        self, session: AsyncSession, source_id: int
    ) -> list[SyncLink]:
        """Return the active sync links whose source channel is ``source_id``."""
        if source_id in self._links_by_source:
            return self._links_by_source[source_id]
        async with self._lock:
            if source_id in self._links_by_source:
                return self._links_by_source[source_id]
            links = await self._query_active_links(session, source_id)
            self._links_by_source[source_id] = links
            return links

    async def get_bot_token(
        self, session: AsyncSession, platform: str, owner_user_id: int
    ) -> str:
        """Return the decrypted bot token for ``platform`` / ``owner_user_id``."""
        key = (platform, owner_user_id)
        if key in self._bot_tokens:
            return self._bot_tokens[key]
        async with self._lock:
            if key in self._bot_tokens:
                return self._bot_tokens[key]
            token = await token_service.resolve_token(session, platform, owner_user_id)
            self._bot_tokens[key] = token
            return token

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------
    def invalidate_channel(self, platform: str | None = None) -> None:
        """Drop cached source channels (optionally only for one platform)."""
        if platform is None:
            self._source_channels.clear()
        else:
            for key in list(self._source_channels):
                if key[0] == platform:
                    self._source_channels.pop(key, None)

    def invalidate_links(self, source_id: int | None = None) -> None:
        """Drop cached links (optionally only for one source)."""
        if source_id is None:
            self._links_by_source.clear()
        else:
            self._links_by_source.pop(source_id, None)

    def invalidate_token(self, platform: str, owner_user_id: int | None = None) -> None:
        """Drop cached tokens (optionally only for one owner)."""
        if owner_user_id is None:
            for key in list(self._bot_tokens):
                if key[0] == platform:
                    self._bot_tokens.pop(key, None)
        else:
            self._bot_tokens.pop((platform, owner_user_id), None)

    def clear(self) -> None:
        """Drop every cached entry (used by tests and full resets)."""
        self._source_channels.clear()
        self._links_by_source.clear()
        self._bot_tokens.clear()

    # ------------------------------------------------------------------
    # Warm-up
    # ------------------------------------------------------------------
    async def warm_up(self, session: AsyncSession) -> None:
        """Preload active source channels, links and tokens at startup."""
        started = asyncio.get_running_loop().time()

        channels = (
            await session.execute(
                select(Channel).where(
                    Channel.role == ChannelRole.SOURCE,
                    Channel.is_active.is_(True),
                )
            )
        ).scalars().all()
        for ch in channels:
            self._source_channels[(ch.platform, ch.platform_channel_id)] = ch

        links = (
            await session.execute(
                select(SyncLink)
                .where(SyncLink.is_active.is_(True))
                .options(
                    selectinload(SyncLink.source_channel),
                    selectinload(SyncLink.destination_channel),
                )
            )
        ).scalars().all()
        for link in links:
            self._links_by_source.setdefault(link.source_channel_id, []).append(link)

        tokens = (await session.execute(select(BotToken))).scalars().all()
        for row in tokens:
            try:
                from app.utils.crypto import get_cipher

                plain = get_cipher().decrypt(row.token)
            except Exception:  # noqa: BLE001
                continue
            self._bot_tokens[(row.platform, row.owner_user_id)] = plain

        elapsed = (asyncio.get_running_loop().time() - started) * 1000
        logger.info(
            "Cache warm-up: {} channels, {} links, {} tokens in {:.1f}ms",
            len(channels),
            len(links),
            len(tokens),
            elapsed,
        )

    async def delete_channel(
        session: AsyncSession,
        channel_id: int,
        user_id: int | None = None,
    ) -> bool:
        """Permanently delete a channel (and its links via cascade).

        If ``user_id`` is provided, only deletes the channel when it belongs to
        that user (prevents cross-user deletion).
        """
        channel = await session.get(Channel, channel_id)
        if channel is None:
            return False
        if user_id is not None and channel.user_id != user_id:
            return False
        await session.delete(channel)
        await session.commit()
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    async def _query_active_links(session: AsyncSession, source_id: int) -> list[SyncLink]:
        stmt = (
            select(SyncLink)
            .where(
                SyncLink.source_channel_id == source_id,
                SyncLink.is_active.is_(True),
            )
            .options(
                selectinload(SyncLink.source_channel),
                selectinload(SyncLink.destination_channel),
            )
        )
        return list((await session.execute(stmt)).scalars().all())


cache_service = CacheService()
