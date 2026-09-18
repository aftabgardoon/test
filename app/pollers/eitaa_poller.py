"""Eitaa poller stub.

Eitaa's official API does **not** support receiving channel messages (no
webhook and no channel update polling). Eitaa can therefore only act as a
*destination* and never as a *source*.

This class exists purely for interface completeness; it is never started
because :meth:`app.adapters.AbstractAdapter.supports_source` is ``False`` for
the Eitaa adapter, and ``start_all_pollers`` skips source-incapable platforms.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.pollers.base import BasePoller


class EitaaPoller(BasePoller):
    """Destination-only stub: Eitaa cannot be polled for source updates."""

    async def _get_updates(self) -> list[dict[str, Any]]:
        """Raise ``NotImplementedError`` — Eitaa has no source updates."""
        raise NotImplementedError("Eitaa is destination-only and cannot be polled")

    async def start(self) -> None:
        """No-op: log that Eitaa cannot be a source and return immediately."""
        logger.warning("Eitaa is destination-only; no poller is started")
        return None
