"""Manager bot polling loop.

The manager bot is the interactive bot users talk to (default platform: Bale).
It polls ``getUpdates`` using long-polling and dispatches raw updates to
:mod:`app.bot_manager.handlers`.

When the manager bot's token also acts as a source listener (same token), the
manager loop is the *only* ``getUpdates`` consumer for that bot, so it also
forwards channel updates to the sync pipeline (see
:func:`app.pollers.base.dispatch_sync_update`).  In that case
:func:`app.pollers.build_polling_adapters` skips the dedicated poller to
avoid double consumption.
"""

from __future__ import annotations

import asyncio

from loguru import logger

from app.adapters import build_adapter
from app.bot_manager import handlers
from app.config import get_settings
from app.database import get_session_factory, init_db
from app.pollers.base import EXPECTED_ERRORS, dispatch_sync_update
from app.utils.logger import setup_logger

# Update keys that carry (potentially source-channel) content.
_CONTENT_KEYS = ("message", "channel_post", "edited_message", "edited_channel_post")


async def run_manager() -> None:
    """Poll for manager-bot updates forever."""
    await init_db()
    settings = get_settings()
    token = settings.manager_bot_token
    platform = settings.manager_bot_platform

    if not token:
        logger.warning("MANAGER_BOT_TOKEN is empty; manager bot is disabled")
        return

    adapter = build_adapter(platform, token)
    if not hasattr(adapter, "get_raw_updates"):
        logger.warning("Manager bot cannot poll on platform {}", platform)
        return

    factory = get_session_factory()
    offset = 0
    consecutive_errors = 0
    logger.info("Manager bot polling started on {}", platform)

    try:
        while True:
            try:
                updates = await adapter.get_raw_updates(  # type: ignore[attr-defined]
                    offset=offset, timeout=settings.polling_timeout
                )
                consecutive_errors = 0
                if updates:
                    logger.debug("Manager received {} update(s)", len(updates))

                for update in updates:
                    offset = int(update.get("update_id", 0)) + 1
                    try:
                        async with factory() as session:
                            await handlers.handle_update(session, adapter, platform, update)
                    except Exception as exc:  # noqa: BLE001 - keep polling alive
                        logger.error(
                            "Manager update handling failed: {}: {}",
                            type(exc).__name__,
                            exc,
                        )

                    # If this bot also listens to source channels (its token
                    # is the MANAGER_BOT_TOKEN), it is the *only* getUpdates
                    # consumer for that bot — so channel updates must be
                    # forwarded to the sync pipeline here (a dedicated poller
                    # is not started for that token; see
                    # app.pollers.build_polling_adapters).
                    if any(key in update for key in _CONTENT_KEYS):
                        try:
                            await dispatch_sync_update(adapter, factory, update)
                        except Exception as exc:  # noqa: BLE001
                            logger.warning(
                                "Sync dispatch failed: {}: {}", type(exc).__name__, exc
                            )
            except asyncio.CancelledError:
                raise
            except EXPECTED_ERRORS as exc:
                consecutive_errors += 1
                delay = min(2**consecutive_errors, 30)
                logger.debug(
                    "manager poller: connection lost ({}); reconnecting in {}s",
                    type(exc).__name__,
                    delay,
                )
                await asyncio.sleep(delay)
            except Exception as exc:  # noqa: BLE001 - keep polling alive
                logger.error("Manager polling error: {}: {}", type(exc).__name__, exc)
                await asyncio.sleep(5)
    finally:
        await adapter.close()


def main() -> None:
    """Entry point for ``python -m app.bot_manager.manager``."""
    setup_logger()
    try:
        asyncio.run(run_manager())
    except KeyboardInterrupt:
        logger.info("Manager stopped")


if __name__ == "__main__":
    main()
