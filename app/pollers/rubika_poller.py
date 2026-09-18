"""Rubika long-polling listener.

Rubika's ``getUpdates`` is paginated with a string ``offset_id`` /
``next_offset_id`` (not Telegram's integer ``update_id``), so this poller keeps
its own ``offset_id`` and passes it to the adapter's ``get_updates_raw``.
"""

from __future__ import annotations

from typing import Any

from app.pollers.base import BasePoller


class RubikaPoller(BasePoller):
    """Poll Rubika via ``getUpdates`` (``offset_id`` pagination)."""

    def __init__(self, adapter, session_factory) -> None:
        super().__init__(adapter, session_factory)
        self._offset_id: str | None = None

    async def _get_updates(self) -> list[dict[str, Any]]:
        updates, next_offset_id = await self.adapter.get_updates_raw(  # type: ignore[attr-defined]
            offset_id=self._offset_id,
            limit=100,
        )
        if next_offset_id:
            self._offset_id = next_offset_id
        return updates
