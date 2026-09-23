"""Bale long-polling listener."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.pollers.base import BasePoller, extract_text_edit
from app.services import sync_service

# Kept for backwards compatibility with tests that import it from here.
_extract_edit = extract_text_edit


class BalePoller(BasePoller):
    """Poll Bale via ``getUpdates`` long polling.

    ``timeout`` keeps the HTTP connection open (long polling) and ``offset``
    is persisted so an update is never processed twice.
    """

    async def _get_updates(self) -> list[dict[str, Any]]:
        settings = get_settings()
        # Note: Bale's documented ``getUpdates`` accepts only ``offset``,
        # ``limit`` and ``timeout`` — there is no ``allowed_updates``
        # parameter (unlike Telegram).  Sending it risks a 400 that would
        # break the whole source poller, so we filter update types on the
        # client side instead (see ``parse_update`` / ``_process_update``).
        updates = await self.adapter.get_raw_updates(  # type: ignore[attr-defined]
            offset=self._offset or None,
            timeout=settings.polling_timeout,
        )
        for update in updates:
            update_id = update.get("update_id")
            if update_id is not None:
                self._offset = max(self._offset, int(update_id) + 1)
        return updates

    async def _process_update(self, update: dict[str, Any]) -> None:
        """Handle edits explicitly to avoid re-posting them as new messages."""
        edit = _extract_edit(update)
        if edit is not None:
            chat_id, message_id, new_text, chat_username = edit
            async with self._session_factory() as session:
                await sync_service.handle_edit(
                    session,
                    self.adapter.platform.value,
                    chat_id,
                    message_id,
                    new_text,
                    chat_username,
                )
            return
        await super()._process_update(update)
