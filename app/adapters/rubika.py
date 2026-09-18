"""Rubika adapter.

Rubika's Bot API is **not** Telegram-compatible. It is a JSON HTTP API:

* Base URL: ``https://botapi.rubika.ir/v3/{token}/{method}`` (POST).
* Docs: https://rubika.ir/botapi

Key differences from Bale/Telegram:

* ``getUpdates`` uses ``offset_id`` / ``next_offset_id`` (strings), not
  ``update_id`` integers.
* An ``Update`` has ``{type, chat_id, new_message | updated_message,
  removed_message_id, event_data}``; a ``Message`` has ``{message_id, text,
  sender_id, file, location, sticker, poll, ...}``.
* Inline buttons use a ``Keypad`` structure (``rows`` → ``buttons`` → ``{id,
  type: "Simple", button_text}``) instead of ``inline_keyboard``.
* Files are sent in two steps: ``requestSendFile`` → ``upload_url`` → upload
  bytes → ``sendFile`` with the returned ``file_id``.

.. warning::
    This is the official-but-unstable Rubika Bot API. The exact request/response
    shapes for the file-upload flow may change; the adapter is isolated behind
    :class:`app.adapters.base.AbstractAdapter` so it can be swapped easily.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import (
    AdapterError,
    BaseHTTPAdapter,
    IncomingMessage,
    InlineKeyboardMarkup,
    MessageType,
    Platform,
    _loads,
)

# FileTypeEnum values accepted by ``requestSendFile``.
_FILE_TYPES = {
    MessageType.PHOTO: "Image",
    MessageType.VIDEO: "Video",
    MessageType.VOICE: "Voice",
    MessageType.AUDIO: "Music",
    MessageType.DOCUMENT: "File",
    MessageType.STICKER: "Image",
}


def _to_keypad(markup: InlineKeyboardMarkup | None) -> dict[str, Any] | None:
    """Convert an inline keyboard to Rubika's ``Keypad`` structure."""
    if not markup or not markup.inline_keyboard:
        return None
    rows = []
    for row in markup.inline_keyboard:
        buttons = []
        for b in row:
            if b.callback_data:
                buttons.append(
                    {"id": b.callback_data, "type": "Simple", "button_text": b.text}
                )
            elif b.url:
                # Link buttons are a best-effort mapping; verify against the API.
                buttons.append({"id": b.url, "type": "Link", "button_text": b.text})
            else:
                buttons.append({"id": b.text, "type": "Simple", "button_text": b.text})
        rows.append({"buttons": buttons})
    return {"rows": rows}


class RubikaAdapter(BaseHTTPAdapter):
    """Rubika Bot API adapter (unofficial)."""

    platform = Platform.RUBIKA
    base_url = "https://botapi.rubika.ir/v3"

    @property
    def supports_edit(self) -> bool:
        return True

    @property
    def supports_delete(self) -> bool:
        return True

    def _api_url(self, method: str) -> str:
        return f"{self.base_url}/{self.token}/{method}"

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    async def send_message(
        self,
        chat_id: str,
        text: str,
        *,
        parse_mode: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str:
        del parse_mode  # Rubika uses `metadata` for formatting, not parse_mode
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        keypad = _to_keypad(reply_markup)
        if keypad:
            payload["inline_keypad"] = keypad
        data = await self._post("sendMessage", **payload)
        return str(data.get("message_id", ""))

    async def _send_file(
        self,
        chat_id: str,
        file_bytes: bytes,
        caption: str | None,
        file_type: str,
    ) -> str:
        """Upload a file (``requestSendFile`` → ``upload_url``) then ``sendFile``."""
        request = await self._post("requestSendFile", type=file_type)
        upload_url = request.get("upload_url")
        file_id = request.get("file_id")

        if upload_url:
            await self._limiter.acquire()
            resp = await self.client.post(upload_url, content=file_bytes)
            if resp.status_code >= 400:
                raise AdapterError(f"Rubika upload failed: HTTP {resp.status_code}")
            if not file_id and resp.content:
                try:
                    file_id = _loads(resp.content).get("file_id")
                except ValueError:
                    file_id = None

        if not file_id:
            raise AdapterError("Rubika could not obtain a file_id for upload")

        payload: dict[str, Any] = {"chat_id": chat_id, "file_id": file_id}
        if caption:
            payload["text"] = caption
        data = await self._post("sendFile", **payload)
        return str(data.get("message_id", ""))

    async def send_photo(
        self,
        chat_id: str,
        file_id_or_bytes: str | bytes,
        *,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str:
        del parse_mode, reply_markup
        return await self._send_file(
            chat_id, self._require_bytes(file_id_or_bytes), caption, "Image"
        )

    async def send_video(
        self,
        chat_id: str,
        file_id_or_bytes: str | bytes,
        *,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str:
        del parse_mode, reply_markup
        return await self._send_file(
            chat_id, self._require_bytes(file_id_or_bytes), caption, "Video"
        )

    async def send_voice(
        self,
        chat_id: str,
        file_id_or_bytes: str | bytes,
        *,
        caption: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str:
        del reply_markup
        return await self._send_file(
            chat_id, self._require_bytes(file_id_or_bytes), caption, "Voice"
        )

    async def send_document(
        self,
        chat_id: str,
        file_id_or_bytes: str | bytes,
        *,
        filename: str | None = None,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str:
        del filename, parse_mode, reply_markup
        return await self._send_file(
            chat_id, self._require_bytes(file_id_or_bytes), caption, "File"
        )

    async def send_sticker(self, chat_id: str, file_id_or_bytes: str | bytes) -> str:
        return await self._send_file(
            chat_id, self._require_bytes(file_id_or_bytes), None, "Image"
        )

    async def send_location(
        self,
        chat_id: str,
        latitude: float,
        longitude: float,
        *,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str:
        del reply_markup
        data = await self._post(
            "sendLocation",
            chat_id=chat_id,
            latitude=str(latitude),
            longitude=str(longitude),
        )
        return str(data.get("message_id", ""))

    async def send_poll(
        self,
        chat_id: str,
        question: str,
        options: list[str],
    ) -> str:
        data = await self._post("sendPoll", chat_id=chat_id, question=question, options=options)
        return str(data.get("message_id", ""))

    async def copy_message(
        self,
        from_chat_id: str,
        chat_id: str,
        message_id: str,
        *,
        caption: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str:
        del from_chat_id, chat_id, message_id, caption, reply_markup
        raise AdapterError("Rubika has no copyMessage; use download + re-upload")

    async def edit_message_text(
        self,
        chat_id: str,
        message_id: str,
        text: str,
        *,
        parse_mode: str | None = None,
    ) -> None:
        del parse_mode
        await self._post("editMessageText", chat_id=chat_id, message_id=message_id, text=text)

    async def delete_message(self, chat_id: str, message_id: str) -> None:
        await self._post("deleteMessage", chat_id=chat_id, message_id=message_id)

    def _require_bytes(self, value: str | bytes) -> bytes:
        if isinstance(value, bytes):
            return value
        raise AdapterError("Rubika cannot resend by file_id; download the file first")

    # ------------------------------------------------------------------
    # Incoming
    # ------------------------------------------------------------------
    async def download_file(self, file_id: str) -> bytes:
        info = await self._post("getFile", file_id=file_id)
        download_url = info.get("download_url")
        if not download_url:
            raise AdapterError(f"Rubika getFile returned no download_url for {file_id}")
        await self._limiter.acquire()
        resp = await self.client.get(download_url)
        if resp.status_code >= 400:
            raise AdapterError(f"Rubika file download failed: HTTP {resp.status_code}")
        return resp.content

    async def get_updates_raw(
        self, offset_id: str | None = None, limit: int = 100
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Return ``(updates, next_offset_id)`` from Rubika's ``getUpdates``."""
        payload: dict[str, Any] = {"limit": limit}
        if offset_id is not None:
            payload["offset_id"] = offset_id
        data = await self._post("getUpdates", **payload)
        return data.get("updates", []), data.get("next_offset_id")

    async def get_me(self) -> dict[str, Any]:
        """Return basic bot info (used for startup warm-up)."""
        return await self._post("getMe")

    async def get_updates(self, offset: int | None = None) -> list[IncomingMessage]:
        del offset
        updates, _ = await self.get_updates_raw()
        messages: list[IncomingMessage] = []
        for update in updates:
            messages.extend(self.parse_update(update))
        return messages

    def parse_update(self, update: dict[str, Any]) -> list[IncomingMessage]:
        update_type = update.get("type", "")
        if update_type == "NewMessage":
            return [self._parse_message(update.get("chat_id", ""), update.get("new_message") or {})]
        if update_type == "UpdatedMessage":
            return [
                self._parse_message(update.get("chat_id", ""), update.get("updated_message") or {})
            ]
        # RemovedMessage / StartedBot / StoppedBot / EventData are not synced.
        return []

    def _parse_message(self, chat_id: str, msg: dict[str, Any]) -> IncomingMessage:
        text = msg.get("text")
        file_info = msg.get("file") or {}
        location = msg.get("location")
        sticker = msg.get("sticker") or {}
        poll = msg.get("poll")

        if text is not None:
            message_type = MessageType.TEXT
            file_id = None
        elif sticker:
            message_type = MessageType.STICKER
            file_id = (sticker.get("file") or {}).get("file_id")
        elif location:
            message_type = MessageType.LOCATION
            file_id = None
        elif poll:
            message_type = MessageType.POLL
            file_id = None
        elif file_info:
            message_type = MessageType.DOCUMENT
            file_id = file_info.get("file_id")
        else:
            message_type = MessageType.OTHER
            file_id = None

        parsed_location = None
        if location:
            parsed_location = {
                "latitude": float(location.get("latitude", 0)),
                "longitude": float(location.get("longitude", 0)),
            }

        return IncomingMessage(
            message_id=str(msg.get("message_id", "")),
            chat_id=str(chat_id),
            from_user_id=str(msg.get("sender_id")) if msg.get("sender_id") else None,
            text=text,
            message_type=message_type,
            file_id=file_id,
            file_name=file_info.get("file_name"),
            location=parsed_location,
            poll=poll,
            sticker={"file_id": file_id} if sticker else None,
            is_forwarded=bool(msg.get("forwarded_from")),
            raw=msg,
        )
