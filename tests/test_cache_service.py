"""Tests for the in-memory cache service."""

from __future__ import annotations

import pytest

from app.models import Channel
from app.models.channel import ChannelRole
from app.schemas.channel import ChannelCreate
from app.services import channel_service, user_service
from app.services.cache_service import cache_service


@pytest.fixture
async def user(db_session):
    return await user_service.get_or_create_user(db_session, "bale", "222", "bob")


async def test_cache_and_invalidation(db_session, user) -> None:
    channel = await channel_service.add_channel(
        db_session,
        user.id,
        ChannelCreate(
            platform="bale",
            platform_channel_id="100",
            title="Source",
            role=ChannelRole.SOURCE,
        ),
    )

    # First read populates the cache.
    cached = await cache_service.get_source_channel(db_session, "bale", "100")
    assert cached is not None
    assert cached.id == channel.id

    # Deactivate the channel in the DB (simulating a user action elsewhere).
    row = await db_session.get(Channel, channel.id)
    row.is_active = False
    await db_session.commit()

    # Without invalidation the cache still returns the stale channel.
    stale = await cache_service.get_source_channel(db_session, "bale", "100")
    assert stale is not None

    # After invalidation the cache re-reads and finds no active source channel.
    cache_service.invalidate_channel("bale")
    refreshed = await cache_service.get_source_channel(db_session, "bale", "100")
    assert refreshed is None


async def test_store_token_invalidates_caches(db_session, user) -> None:
    """Replacing a token must clear both the token cache and the adapter cache."""
    from app.adapters import build_adapter
    from app.services import sync_service, token_service

    # Simulate stale caches as they would exist in a running worker.
    cache_service._bot_tokens[("bale", user.id)] = "OLD-TOKEN"
    sync_service._adapter_cache[("bale", user.id)] = build_adapter("bale", "OLD-TOKEN")

    # Store a new token: both caches must be invalidated.
    await token_service.store_token(db_session, "bale", "NEW-TOKEN", owner_user_id=user.id)
    assert ("bale", user.id) not in cache_service._bot_tokens
    assert ("bale", user.id) not in sync_service._adapter_cache

    # The next read must resolve the NEW token from the DB, not the stale one.
    fresh = await cache_service.get_bot_token(db_session, "bale", user.id)
    assert fresh == "NEW-TOKEN"
