"""Rubika long-polling listener.

Rubika's ``getUpdates`` is paginated with a string ``offset_id`` /
``next_offset_id`` (not Telegram's integer ``update_id``), so this poller keeps
its own ``offset_id`` and passes it to the adapter's ``get_updates_raw``.

Unlike Bale, Rubika's ``getUpdates`` returns immediately (it has no
long-polling ``timeout`` parameter), so this poller sleeps
``settings.polling_interval`` between empty polls to avoid hammering the API.

It also routes ``UpdatedMessage`` events to edit propagation (the adapter's
``parse_update`` deliberately skips them) and ``RemovedMessage`` events to
delete propagation.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.config import get_settings
from app.pollers.base import BasePoller
from app.services import sync_service


class RubikaPoller(BasePoller):
    """Poll Rubika via ``getUpdates`` (``offset_id`` pagination)."""

    def __init__(self, adapter, session_factory) -> None:
        super().__init__(adapter, session_factory)
        self._offset_id: str | None = None
        # Rubika getUpdates is not long-polling: sleep when the batch is empty.
        self.poll_interval = get_settings().polling_interval

    async def _get_updates(self) -> list[dict[str, Any]]:
        updates, next_offset_id = await self.adapter.get_updates_raw(  # type: ignore[attr-defined]
            offset_id=self._offset_id,
            limit=100,
        )
        if next_offset_id:
            self._offset_id = next_offset_id
        return updates

    async def _process_update(self, update: dict[str, Any]) -> None:
        """Route edits and deletions before the generic new-message path."""
        update_type = update.get("type", "")
        chat_id = str(update.get("chat_id", ""))

        if update_type == "UpdatedMessage":
            msg = update.get("updated_message") or {}
            message_id = str(msg.get("message_id", ""))
            new_text = msg.get("text")
            if chat_id and message_id and new_text:
                async with self._session_factory() as session:
                    await sync_service.handle_edit(
                        session,
                        self.adapter.platform.value,
                        chat_id,
                        message_id,
                        new_text,
                    )
            return

        if update_type == "RemovedMessage":
            removed_id = str(update.get("removed_message_id") or "")
            if chat_id and removed_id:
                async with self._session_factory() as session:
                    await sync_service.handle_delete(
                        session,
                        self.adapter.platform.value,
                        chat_id,
                        removed_id,
                    )
            return

        await super()._process_update(update)

    async def stop(self) -> None:  # pragma: no cover - logging only
        await super().stop()
        logger.debug("rubika poller stopped")
