"""Pollers package: long-polling listeners for source platforms.

Each poller wraps a platform :class:`~app.adapters.AbstractAdapter` and polls
the messenger for new updates, normalising them into
:class:`~app.adapters.IncomingMessage` and feeding them to the sync service.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from loguru import logger

from app.adapters import AbstractAdapter, Platform, build_adapter
from app.config import get_settings
from app.pollers.bale_poller import BalePoller
from app.pollers.base import BasePoller
from app.pollers.eitaa_poller import EitaaPoller
from app.pollers.rubika_poller import RubikaPoller

# Mapping from platform to its poller implementation.
_POLLERS: dict[Platform, type[BasePoller]] = {
    Platform.BALE: BalePoller,
    Platform.RUBIKA: RubikaPoller,
    Platform.EITAA: EitaaPoller,
}


def build_polling_adapters() -> dict[Platform, AbstractAdapter]:
    """Build one adapter per configured platform token.

    Only platforms with a non-empty token are returned. Eitaa is skipped by
    the caller because it cannot act as a source.
    """
    settings = get_settings()
    tokens: dict[Platform, str] = {
        Platform.BALE: settings.bale_bot_token,
        Platform.RUBIKA: settings.rubika_bot_token,
        Platform.EITAA: settings.eitaa_bot_token,
    }
    adapters: dict[Platform, AbstractAdapter] = {}
    for platform, token in tokens.items():
        if token:
            adapters[platform] = build_adapter(platform, token)
    return adapters


async def start_all_pollers(
    adapters: dict[Platform, AbstractAdapter],
    session_factory: Callable,
) -> list[asyncio.Task]:
    """Create and start a poller task for every source-capable adapter.

    Args:
        adapters: Mapping of platform to adapter instance.
        session_factory: Async session factory used to open a fresh DB session
            per update.

    Returns:
        The list of running poller tasks (cancel them on shutdown).
    """
    tasks: list[asyncio.Task] = []
    for platform, adapter in adapters.items():
        if not adapter.supports_source:
            logger.info("Skipping poller for {} (destination-only)", platform.value)
            continue

        poller_cls = _POLLERS.get(platform)
        if poller_cls is None:
            logger.warning("No poller implementation for platform {}", platform.value)
            continue

        poller = poller_cls(adapter, session_factory)
        tasks.append(asyncio.create_task(poller.start(), name=f"poller-{platform.value}"))

    return tasks


__all__ = [
    "BasePoller",
    "BalePoller",
    "EitaaPoller",
    "RubikaPoller",
    "build_polling_adapters",
    "start_all_pollers",
]
