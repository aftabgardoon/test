"""Manager bot polling loop.

The manager bot is the interactive bot users talk to (default platform: Bale).
It polls ``getUpdates`` using long-polling and dispatches raw updates to
:mod:`app.bot_manager.handlers`.
"""

from __future__ import annotations

import asyncio

from loguru import logger

from app.adapters import build_adapter
from app.bot_manager import handlers
from app.config import get_settings
from app.database import get_session_factory, init_db
from app.pollers.base import EXPECTED_ERRORS
from app.utils.logger import setup_logger


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
                async with factory() as session:
                    await handlers.handle_update(session, adapter, platform, update)
        except asyncio.CancelledError:
            raise
        except EXPECTED_ERRORS as exc:
            consecutive_errors += 1
            delay = min(2 ** consecutive_errors, 30)
            logger.debug(
                "manager poller: connection lost ({}); reconnecting in {}s",
                type(exc).__name__,
                delay,
            )
            await asyncio.sleep(delay)
        except Exception as exc:  # noqa: BLE001 - keep polling alive
            logger.error("Manager polling error: {}: {}", type(exc).__name__, exc)
            await asyncio.sleep(5)


def main() -> None:
    """Entry point for ``python -m app.bot_manager.manager``."""
    setup_logger()
    try:
        asyncio.run(run_manager())
    except KeyboardInterrupt:
        logger.info("Manager stopped")


if __name__ == "__main__":
    main()
