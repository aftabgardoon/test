"""Eitaa adapter.

Eitaa exposes a simple HTTP API:

* Base URL: ``https://eitaayar.ir/api/<TOKEN>/METHOD``
* Docs: https://eitaayar.ir/api

**Important notes:**

* Eitaa does **not** provide "bots" like Bale/Rubika. Instead you create an
  **app (برنامک)** whose token works differently — but the send-side HTTP API
  (`sendMessage`, `sendFile`, `sendPoll`, ...) is the one wrapped here.
* The official Eitaa API does not allow receiving channel messages via webhook
  or live updates, so Eitaa is only supported as a *destination* and never as a
  *source*. This is enforced by ``supports_source`` returning ``False``.

Eitaa has no ``copyMessage``; media must be downloaded from the source and
re-uploaded via ``sendFile``.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import (
    AdapterError,
    BaseHTTPAdapter,
    IncomingMessage,
    InlineKeyboardMarkup,
    Platform,
)


class EitaaAdapter(BaseHTTPAdapter):
    """Destination-only adapter for Eitaa."""

    platform = Platform.EITAA
    base_url = "https://eitaayar.ir/api"

    @property
    def supports_source(self) -> bool:
        return False

    def _api_url(self, method: str) -> str:
        return f"{self.base_url}/{self.token}/{method}"

    def _require_bytes(self, value: str | bytes) -> bytes:
        if isinstance(value, bytes):
            return value
        raise AdapterError(
            "Eitaa cannot resend by file_id; download the file first and pass bytes"
        )

    async def _upload(
        self,
        chat_id: str,
        file_bytes: bytes,
        filename: str,
        *,
        caption: str | None = None,
    ) -> str:
        await self._limiter.acquire()
        data: dict[str, str] = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        files = {"file": (filename, file_bytes)}
        try:
            resp = await self.client.post(self._api_url("sendFile"), data=data, files=files)
        except httpx.HTTPError as exc:
            raise AdapterError(f"Eitaa upload failed: {exc}") from exc
        return self._extract_message_id(resp)

    def _extract_message_id(self, resp: httpx.Response) -> str:
        if resp.status_code >= 400:
            raise AdapterError(f"Eitaa HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise AdapterError(f"Eitaa returned non-JSON: {resp.text[:200]}") from exc
        if isinstance(data, dict):
            if data.get("ok") is False:
                raise AdapterError(f"Eitaa API error: {data.get('error', data)}")
            result = data.get("result") or {}
            if isinstance(result, dict) and result.get("message_id") is not None:
                return str(result["message_id"])
        # Some endpoints return the message id directly.
        return str(data)

    async def send_message(
        self,
        chat_id: str,
        text: str,
        *,
        parse_mode: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str:
        # Eitaa ignores reply_markup; kept in the signature for interface parity.
        del reply_markup
        await self._limiter.acquire()
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        try:
            resp = await self.client.post(self._api_url("sendMessage"), data=payload)
        except httpx.HTTPError as exc:
            raise AdapterError(f"Eitaa sendMessage failed: {exc}") from exc
        return self._extract_message_id(resp)

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
        return await self._upload(
            chat_id, self._require_bytes(file_id_or_bytes), "photo.jpg", caption=caption
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
        return await self._upload(
            chat_id, self._require_bytes(file_id_or_bytes), "video.mp4", caption=caption
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
        return await self._upload(
            chat_id, self._require_bytes(file_id_or_bytes), "voice.ogg", caption=caption
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
        del parse_mode, reply_markup
        name = filename or "document"
        return await self._upload(
            chat_id, self._require_bytes(file_id_or_bytes), name, caption=caption
        )

    async def send_sticker(
        self,
        chat_id: str,
        file_id_or_bytes: str | bytes,
    ) -> str:
        return await self._upload(
            chat_id, self._require_bytes(file_id_or_bytes), "sticker.webp"
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
        text = f"📍 {latitude}, {longitude}"
        return await self.send_message(chat_id, text)

    async def send_poll(
        self,
        chat_id: str,
        question: str,
        options: list[str],
    ) -> str:
        await self._limiter.acquire()
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "question": question,
            "options": options,
        }
        try:
            resp = await self.client.post(self._api_url("sendPoll"), data=payload)
        except httpx.HTTPError as exc:
            raise AdapterError(f"Eitaa sendPoll failed: {exc}") from exc
        return self._extract_message_id(resp)

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
        raise AdapterError("Eitaa does not support copyMessage")

    async def download_file(self, file_id: str) -> bytes:
        del file_id
        raise AdapterError("Eitaa is destination-only and cannot download files")

    async def get_updates(self, offset: int | None = None) -> list[IncomingMessage]:
        del offset
        raise AdapterError("Eitaa does not support receiving updates (destination-only)")

    def parse_update(self, update: dict[str, Any]) -> list[IncomingMessage]:
        del update
        return []
