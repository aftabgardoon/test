"""Bale long-polling listener."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.pollers.base import BasePoller
from app.services import sync_service

# All update types relevant to channel synchronisation.
ALLOWED_UPDATES = [
    "message",
    "channel_post",
    "edited_message",
    "edited_channel_post",
    "callback_query",
]


def _extract_edit(update: dict[str, Any]) -> tuple[str, str, str] | None:
    """Return ``(chat_id, message_id, new_text)`` for an edit update, if any."""
    for key in ("edited_message", "edited_channel_post"):
        msg = update.get(key)
        if isinstance(msg, dict) and msg.get("text"):
            chat_id = str((msg.get("chat") or {}).get("id", ""))
            message_id = str(msg.get("message_id", ""))
            return chat_id, message_id, msg["text"]
    return None


class BalePoller(BasePoller):
    """Poll Bale via ``getUpdates`` long polling.

    ``timeout`` keeps the HTTP connection open (long polling) and ``offset``
    is persisted so an update is never processed twice.
    """

    async def _get_updates(self) -> list[dict[str, Any]]:
        settings = get_settings()
        updates = await self.adapter.get_raw_updates(  # type: ignore[attr-defined]
            offset=self._offset or None,
            timeout=settings.polling_timeout,
            allowed_updates=ALLOWED_UPDATES,
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
            chat_id, message_id, new_text = edit
            async with self._session_factory() as session:
                await sync_service.handle_edit(
                    session,
                    self.adapter.platform.value,
                    chat_id,
                    message_id,
                    new_text,
                )
            return
        await super()._process_update(update)
