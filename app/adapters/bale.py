"""Bale adapter.

Bale exposes a Telegram-compatible Bot API:

* Base URL: ``https://tapi.bale.ai/bot<TOKEN>/METHOD``
* File URL: ``https://tapi.bale.ai/file/bot<TOKEN>/<file_path>``
* Docs: https://docs.bale.ai

Bale supports ``copyMessage`` which copies a message *without* the
"forwarded from" label, preserving caption and inline keyboard. It also
supports editing and deleting messages, so it can act as both source and
destination.
"""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from app.adapters.base import (
    AdapterError,
    BaseHTTPAdapter,
    IncomingMessage,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MessageType,
    Platform,
    _dumps,
)

_HTML_ENTITY_TYPES = {
    "bold",
    "italic",
    "code",
    "pre",
    "text_link",
    "underline",
    "strikethrough",
    "spoiler",
}


def _build_keyboard(markup: dict[str, Any] | None) -> InlineKeyboardMarkup | None:
    """Convert a Telegram/Bale ``inline_keyboard`` dict into our model."""
    if not markup or "inline_keyboard" not in markup:
        return None
    rows: list[list[InlineKeyboardButton]] = []
    for row in markup["inline_keyboard"]:
        buttons = [
            InlineKeyboardButton(
                text=btn.get("text", ""),
                url=btn.get("url"),
                callback_data=btn.get("callback_data"),
            )
            for btn in row
        ]
        rows.append(buttons)
    return InlineKeyboardMarkup(inline_keyboard=rows)


class BaleAdapter(BaseHTTPAdapter):
    """Bot API adapter for Bale."""

    platform = Platform.BALE
    base_url = "https://tapi.bale.ai"

    @property
    def supports_copy_message(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Bale-specific request handling
    # ------------------------------------------------------------------
    async def _post(self, method: str, **kwargs: Any) -> dict[str, Any]:
        """POST to Bale, dropping parameters Bale's API does not document.

        * ``None`` values are removed — Telegram-style APIs reject unexpected
          parameters (``caption: null``, ``reply_markup: null``, ...), and the
          Bale docs state that an ``InlineKeyboardButton`` may carry *only one*
          of its optional fields (``url`` / ``callback_data`` / ...).
        * ``parse_mode`` is never sent: Bale renders *all* outgoing text as
          Markdown and its method documentation defines no ``parse_mode``
          parameter (sending it risks a 400 for the whole request).
        """
        clean: dict[str, Any] = {}
        for key, value in kwargs.items():
            if value is None or key == "parse_mode":
                continue
            clean[key] = value
        return await super()._post(method, **clean)

    @property
    def supports_edit(self) -> bool:
        return True

    @property
    def supports_delete(self) -> bool:
        return True

    def _file_url(self, file_path: str) -> str:
        return f"{self.base_url}/file/bot{self.token}/{file_path}"

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
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup.model_dump(exclude_none=True)
        data = await self._post("sendMessage", **payload)
        return str(data["result"]["message_id"])

    async def _send_media(
        self,
        method: str,
        field: str,
        chat_id: str,
        value: str | bytes,
        *,
        filename: str,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str:
        """Send a media message using ``file_id`` (JSON) or raw bytes (multipart)."""
        await self._limiter.acquire()
        url = self._api_url(method)
        data: dict[str, Any] = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        if parse_mode:
            data["parse_mode"] = parse_mode
        if reply_markup:
            data["reply_markup"] = reply_markup.model_dump(exclude_none=True)

        try:
            if isinstance(value, str):
                data[field] = value
                resp = await self.client.post(url, json=data)
            else:
                # multipart/form-data: reply_markup must be a JSON string.
                form = dict(data)
                if "reply_markup" in form:
                    form["reply_markup"] = _dumps(form["reply_markup"]).decode("utf-8")
                files = {field: (filename, value)}
                resp = await self.client.post(url, data=form, files=files)
        except httpx.HTTPError as exc:
            raise AdapterError(f"{self.platform} {method} failed: {exc}") from exc

        payload = self._parse_response(resp)
        return str(payload["result"]["message_id"])

    async def send_photo(
        self,
        chat_id: str,
        file_id_or_bytes: str | bytes,
        *,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str:
        return await self._send_media(
            "sendPhoto",
            "photo",
            chat_id,
            file_id_or_bytes,
            filename="photo.jpg",
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
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
        return await self._send_media(
            "sendVideo",
            "video",
            chat_id,
            file_id_or_bytes,
            filename="video.mp4",
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )

    async def send_voice(
        self,
        chat_id: str,
        file_id_or_bytes: str | bytes,
        *,
        caption: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str:
        return await self._send_media(
            "sendVoice",
            "voice",
            chat_id,
            file_id_or_bytes,
            filename="voice.ogg",
            caption=caption,
            reply_markup=reply_markup,
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
        return await self._send_media(
            "sendDocument",
            "document",
            chat_id,
            file_id_or_bytes,
            filename=filename or "document",
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )

    async def send_audio(
        self,
        chat_id: str,
        file_id_or_bytes: str | bytes,
        *,
        filename: str | None = None,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str:
        # Per the docs (sendAudio): the file must be .MP3 or .M4A and is
        # shown in the client's music player (unlike a generic document).
        return await self._send_media(
            "sendAudio",
            "audio",
            chat_id,
            file_id_or_bytes,
            filename=filename or "audio.mp3",
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )

    async def send_sticker(
        self,
        chat_id: str,
        file_id_or_bytes: str | bytes,
    ) -> str:
        # sendSticker is not in Bale's documented method list.  Try it first
        # (Bale is a Telegram-style API and may support it), then degrade
        # gracefully so the sticker still reaches the destination as an
        # image (photo) or, failing that, as a document.
        try:
            return await self._send_media(
                "sendSticker",
                "sticker",
                chat_id,
                file_id_or_bytes,
                filename="sticker.webp",
            )
        except AdapterError as sticker_exc:
            logger.debug("sendSticker failed ({}); falling back", sticker_exc)
        try:
            # Works with raw bytes (cross-platform) or a Bale file_id.
            return await self.send_photo(chat_id, file_id_or_bytes)
        except AdapterError as photo_exc:
            logger.debug("photo fallback failed ({}); using document", photo_exc)
        return await self.send_document(chat_id, file_id_or_bytes, filename="sticker.webp")

    async def send_location(
        self,
        chat_id: str,
        latitude: float,
        longitude: float,
        *,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str:
        data = await self._post(
            "sendLocation",
            chat_id=chat_id,
            latitude=latitude,
            longitude=longitude,
            reply_markup=reply_markup.model_dump(exclude_none=True) if reply_markup else None,
        )
        return str(data["result"]["message_id"])

    async def send_poll(
        self,
        chat_id: str,
        question: str,
        options: list[str],
    ) -> str:
        # Bale's documented method list has no sendPoll — render the poll as
        # plain text so poll messages are still delivered.
        lines = [question or "نظرسنجی"]
        lines.extend(f"{index}. {option}" for index, option in enumerate(options, start=1))
        return await self.send_message(chat_id, "\n".join(lines))

    async def copy_message(
        self,
        from_chat_id: str,
        chat_id: str,
        message_id: str,
        *,
        caption: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str:
        # Bale's documented copyMessage takes EXACTLY chat_id / from_chat_id /
        # message_id — no caption, no reply_markup.  The copy already carries
        # the original message's caption and keyboard, so those parameters
        # are accepted for interface parity but deliberately not sent
        # (an undocumented parameter risks a 400 for the whole request).
        del caption, reply_markup
        data = await self._post(
            "copyMessage",
            from_chat_id=from_chat_id,
            chat_id=chat_id,
            message_id=message_id,
        )
        return str(data["result"]["message_id"])

    async def edit_message_text(
        self,
        chat_id: str,
        message_id: str,
        text: str,
        *,
        parse_mode: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        await self._post("editMessageText", **payload)

    async def delete_message(self, chat_id: str, message_id: str) -> None:
        await self._post("deleteMessage", chat_id=chat_id, message_id=message_id)

    # ------------------------------------------------------------------
    # Incoming
    # ------------------------------------------------------------------
    async def download_file(self, file_id: str) -> bytes:
        info = await self._post("getFile", file_id=file_id)
        file_path = info["result"].get("file_path")
        if not file_path:
            raise AdapterError(f"Bale getFile returned no file_path for {file_id}")
        await self._limiter.acquire()
        resp = await self.client.get(self._file_url(file_path))
        if resp.status_code >= 400:
            raise AdapterError(f"Bale file download failed: HTTP {resp.status_code}")
        return resp.content

    async def get_updates(self, offset: int | None = None) -> list[IncomingMessage]:
        messages: list[IncomingMessage] = []
        for update in await self.get_raw_updates(offset):
            messages.extend(self.parse_update(update))
        return messages

    async def get_raw_updates(
        self,
        offset: int | None = None,
        timeout: int = 30,
        allowed_updates: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return raw update dicts (including ``callback_query`` events)."""
        del allowed_updates  # Bale's getUpdates has no such parameter; ignored.
        params: dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        data = await self._get("getUpdates", **params)
        return data.get("result", [])

    async def get_me(self) -> dict[str, Any]:
        """Return basic bot info (used for startup warm-up)."""
        data = await self._get("getMe")
        return data.get("result", {})

    async def answer_callback_query(self, callback_query_id: str, text: str | None = None) -> None:
        """Dismiss a callback query (optionally showing a toast)."""
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        await self._post("answerCallbackQuery", **payload)

    def parse_update(self, update: dict[str, Any]) -> list[IncomingMessage]:
        # Only *new* content is parsed here.  ``edited_message`` /
        # ``edited_channel_post`` are deliberately excluded: text edits are
        # routed to edit propagation by the poller / manager loop, and
        # emitting non-text edits (e.g. a changed photo caption) as new
        # messages would duplicate the post in destination channels (same
        # design decision as the Rubika adapter).
        for key in ("message", "channel_post"):
            if key in update and isinstance(update[key], dict):
                return [self._parse_message(update[key])]
        return []

    def _parse_message(self, msg: dict[str, Any]) -> IncomingMessage:
        chat = msg.get("chat") or {}
        message_id = str(msg.get("message_id", ""))
        chat_id = str(chat.get("id", ""))

        message_type, file_id = self._detect_type(msg)
        parse_mode = None
        if msg.get("entities") and any(
            e.get("type") in _HTML_ENTITY_TYPES for e in msg["entities"]
        ):
            parse_mode = "HTML"

        location = None
        if "location" in msg:
            location = {
                "latitude": float(msg["location"].get("latitude", 0)),
                "longitude": float(msg["location"].get("longitude", 0)),
            }

        document = msg.get("document") or {}
        sticker = msg.get("sticker") or {}

        sender = msg.get("from") or {}
        return IncomingMessage(
            message_id=message_id,
            chat_id=chat_id,
            chat_username=chat.get("username"),
            from_user_id=str(sender["id"]) if sender.get("id") is not None else None,
            text=msg.get("text"),
            caption=msg.get("caption"),
            message_type=message_type,
            file_id=file_id,
            file_name=document.get("file_name"),
            mime_type=document.get("mime_type"),
            location=location,
            poll=msg.get("poll"),
            sticker={"file_id": sticker.get("file_id")} if sticker else None,
            reply_markup=_build_keyboard(msg.get("reply_markup")),
            parse_mode=parse_mode,
            is_forwarded=bool(
                msg.get("forward_from")
                or msg.get("forward_from_chat")
                or msg.get("forward_origin")
            ),
            raw=msg,
        )

    @staticmethod
    def _detect_type(msg: dict[str, Any]) -> tuple[MessageType, str | None]:
        """Return the message type and the best downloadable ``file_id``."""
        if "text" in msg:
            return MessageType.TEXT, None
        if "photo" in msg:
            largest = max(msg["photo"], key=lambda p: p.get("file_size", 0))
            return MessageType.PHOTO, largest.get("file_id")
        if "video" in msg:
            return MessageType.VIDEO, msg["video"].get("file_id")
        if "voice" in msg:
            return MessageType.VOICE, msg["voice"].get("file_id")
        if "audio" in msg:
            return MessageType.AUDIO, msg["audio"].get("file_id")
        if "document" in msg:
            return MessageType.DOCUMENT, msg["document"].get("file_id")
        if "sticker" in msg:
            return MessageType.STICKER, msg["sticker"].get("file_id")
        if "location" in msg:
            return MessageType.LOCATION, None
        if "poll" in msg:
            return MessageType.POLL, None
        return MessageType.OTHER, None
