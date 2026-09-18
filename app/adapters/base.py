"""Adapter abstractions: shared types and the :class:`AbstractAdapter` interface.

Every messenger (Bale, Eitaa, Rubika) is wrapped behind the same interface so
the synchronisation core never knows which concrete platform it talks to.
Adding a new platform means implementing :class:`AbstractAdapter` and
registering it in :mod:`app.adapters`.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from app.config import get_settings

try:  # orjson is much faster than stdlib json; fall back gracefully if missing
    import orjson as _json
except ImportError:  # pragma: no cover - optional dependency
    import json as _json  # type: ignore[no-redef]


def _dumps(payload: Any) -> bytes:
    """Serialize ``payload`` to JSON bytes (orjson if available)."""
    if _json.__name__ == "orjson":
        return _json.dumps(payload)  # type: ignore[union-attr]
    import json

    return json.dumps(payload).encode("utf-8")


def _loads(content: bytes) -> Any:
    """Deserialize JSON bytes (orjson if available)."""
    if _json.__name__ == "orjson":
        return _json.loads(content)  # type: ignore[union-attr]
    import json

    return json.loads(content.decode("utf-8"))


class Platform(StrEnum):
    """Supported messenger platforms."""

    BALE = "bale"
    EITAA = "eitaa"
    RUBIKA = "rubika"


class MessageType(StrEnum):
    """Canonical message types understood by the sync engine."""

    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    VOICE = "voice"
    AUDIO = "audio"
    DOCUMENT = "document"
    STICKER = "sticker"
    LOCATION = "location"
    POLL = "poll"
    FORWARDED = "forwarded"
    OTHER = "other"


class InlineKeyboardButton(BaseModel):
    """A single inline keyboard button."""

    text: str
    url: str | None = None
    callback_data: str | None = None


class InlineKeyboardMarkup(BaseModel):
    """Inline keyboard markup (row-major)."""

    inline_keyboard: list[list[InlineKeyboardButton]] = Field(default_factory=list)


class IncomingMessage(BaseModel):
    """Normalised representation of an incoming message."""

    message_id: str
    chat_id: str
    from_user_id: str | None = None
    text: str | None = None
    caption: str | None = None
    message_type: MessageType = MessageType.OTHER
    file_id: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    location: dict[str, float] | None = None
    poll: dict[str, Any] | None = None
    sticker: dict[str, Any] | None = None
    reply_markup: InlineKeyboardMarkup | None = None
    parse_mode: str | None = None
    is_forwarded: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)
    received_at: float | None = None

    @property
    def has_file(self) -> bool:
        """Return ``True`` when the message carries a downloadable file."""
        return self.file_id is not None


class AdapterError(Exception):
    """Base error raised by adapters when a platform call fails."""


class TransientError(AdapterError):
    """A temporary network error (connection drop, timeout) worth retrying quietly."""


# httpx errors that are expected during polling and should be retried silently.
_TRANSIENT_HTTP_ERRORS = (
    httpx.RemoteProtocolError,
    httpx.ReadError,
    httpx.ReadTimeout,
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.WriteError,
    httpx.PoolTimeout,
)


class RateLimiter:
    """Semaphore-based rate limiter (no ``asyncio.sleep`` in the request path).

    A semaphore starts with ``rps`` tokens; a background task refills one token
    every ``1 / rps`` seconds. When the semaphore is empty, awaiting callers
    block on the semaphore (yielding to the event loop) while unrelated tasks
    keep running.
    """

    def __init__(self, rps: int) -> None:
        self._rps = max(1, rps)
        self._interval = 1.0 / self._rps
        self._semaphore = asyncio.Semaphore(self._rps)
        self._refill_task: asyncio.Task | None = None

    async def _refill_loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            try:
                self._semaphore.release()
            except ValueError:
                pass  # already at capacity

    async def acquire(self) -> None:
        """Wait until a request slot is available."""
        if self._refill_task is None:
            self._refill_task = asyncio.create_task(self._refill_loop())
        await self._semaphore.acquire()

    async def close(self) -> None:
        """Cancel the refill task."""
        if self._refill_task is not None:
            self._refill_task.cancel()
            self._refill_task = None


class AbstractAdapter(ABC):
    """Common interface implemented by all platform adapters."""

    platform: Platform

    def __init__(self, token: str, rps: int = 30) -> None:
        if not token:
            raise AdapterError(f"Missing token for {self.platform} adapter")
        self.token = token
        self._limiter = RateLimiter(rps)

    # ------------------------------------------------------------------
    # Capability flags
    # ------------------------------------------------------------------
    @property
    def supports_copy_message(self) -> bool:
        """Whether ``copy_message`` is available (preserves appearance)."""
        return False

    @property
    def supports_edit(self) -> bool:
        """Whether ``edit_message_text`` is supported."""
        return False

    @property
    def supports_delete(self) -> bool:
        """Whether ``delete_message`` is supported."""
        return False

    @property
    def supports_source(self) -> bool:
        """Whether this platform can act as a *source* of updates."""
        return True

    # ------------------------------------------------------------------
    # Outgoing messages (return destination message id)
    # ------------------------------------------------------------------
    @abstractmethod
    async def send_message(
        self,
        chat_id: str,
        text: str,
        *,
        parse_mode: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str: ...

    @abstractmethod
    async def send_photo(
        self,
        chat_id: str,
        file_id_or_bytes: str | bytes,
        *,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str: ...

    @abstractmethod
    async def send_video(
        self,
        chat_id: str,
        file_id_or_bytes: str | bytes,
        *,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str: ...

    @abstractmethod
    async def send_voice(
        self,
        chat_id: str,
        file_id_or_bytes: str | bytes,
        *,
        caption: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str: ...

    @abstractmethod
    async def send_document(
        self,
        chat_id: str,
        file_id_or_bytes: str | bytes,
        *,
        filename: str | None = None,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str: ...

    @abstractmethod
    async def send_sticker(
        self,
        chat_id: str,
        file_id_or_bytes: str | bytes,
    ) -> str: ...

    @abstractmethod
    async def send_location(
        self,
        chat_id: str,
        latitude: float,
        longitude: float,
        *,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str: ...

    @abstractmethod
    async def send_poll(
        self,
        chat_id: str,
        question: str,
        options: list[str],
    ) -> str: ...

    @abstractmethod
    async def copy_message(
        self,
        from_chat_id: str,
        chat_id: str,
        message_id: str,
        *,
        caption: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> str: ...

    async def edit_message_text(
        self,
        chat_id: str,
        message_id: str,
        text: str,
        *,
        parse_mode: str | None = None,
    ) -> None:
        """Edit a message; raises :class:`AdapterError` if unsupported."""
        raise AdapterError(f"{self.platform} does not support editing messages")

    async def delete_message(self, chat_id: str, message_id: str) -> None:
        """Delete a message; raises :class:`AdapterError` if unsupported."""
        raise AdapterError(f"{self.platform} does not support deleting messages")

    # ------------------------------------------------------------------
    # Incoming / file helpers
    # ------------------------------------------------------------------
    @abstractmethod
    async def download_file(self, file_id: str) -> bytes: ...

    @abstractmethod
    async def get_updates(self, offset: int | None = None) -> list[IncomingMessage]: ...

    @abstractmethod
    def parse_update(self, update: dict[str, Any]) -> list[IncomingMessage]:
        """Parse a raw ``getUpdates`` item into messages."""


class BaseHTTPAdapter(AbstractAdapter):
    """Shared HTTP plumbing for JSON/REST-style bot APIs with pooling."""

    base_url: str = ""

    def __init__(
        self,
        token: str,
        rps: int = 30,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(token, rps)
        self._client = client
        self._owns_client = client is None

    def _build_client(self) -> httpx.AsyncClient:
        """Create a pooled, keep-alive ``httpx.AsyncClient``."""
        settings = get_settings()
        timeout = httpx.Timeout(
            connect=10.0,
            read=settings.polling_timeout + 10.0,
            write=10.0,
            pool=10.0,
        )
        limits = httpx.Limits(
            max_keepalive_connections=5,
            max_connections=20,
            keepalive_expiry=60.0,
        )
        return httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            headers={"Connection": "keep-alive"},
        )

    @property
    def client(self) -> httpx.AsyncClient:
        """Return the underlying HTTP client, creating it lazily."""
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _api_url(self, method: str) -> str:
        """Return the full URL for ``method`` on this platform."""
        return f"{self.base_url}/bot{self.token}/{method}"

    async def _post(self, method: str, **kwargs: Any) -> dict[str, Any]:
        """POST JSON ``kwargs`` to ``method`` and parse the JSON response."""
        await self._limiter.acquire()
        url = self._api_url(method)
        t0 = time.perf_counter()
        try:
            resp = await self.client.post(
                url,
                content=_dumps(kwargs),
                headers={"Content-Type": "application/json"},
            )
        except _TRANSIENT_HTTP_ERRORS as exc:
            raise TransientError(f"{self.platform} transient: {exc}") from exc
        except httpx.HTTPError as exc:
            raise AdapterError(f"{self.platform} request failed: {exc}") from exc
        finally:
            logger.debug(
                "[LATENCY] {} {} http={:.2f}ms",
                self.platform.value,
                method,
                (time.perf_counter() - t0) * 1000,
            )
        return self._parse_response(resp)

    async def _get(self, method: str, **kwargs: Any) -> dict[str, Any]:
        """GET ``method`` and parse the JSON response."""
        await self._limiter.acquire()
        url = self._api_url(method)
        t0 = time.perf_counter()
        try:
            resp = await self.client.get(url, params=kwargs)
        except _TRANSIENT_HTTP_ERRORS as exc:
            raise TransientError(f"{self.platform} transient: {exc}") from exc
        except httpx.HTTPError as exc:
            raise AdapterError(f"{self.platform} request failed: {exc}") from exc
        finally:
            logger.debug(
                "[LATENCY] {} {} http={:.2f}ms",
                self.platform.value,
                method,
                (time.perf_counter() - t0) * 1000,
            )
        return self._parse_response(resp)

    def _parse_response(self, resp: httpx.Response) -> dict[str, Any]:
        """Validate a raw HTTP response and return its JSON body."""
        if resp.status_code >= 400:
            raise AdapterError(
                f"{self.platform} HTTP {resp.status_code}: {resp.text[:300]}"
            )
        try:
            data = _loads(resp.content)
        except ValueError as exc:
            raise AdapterError(f"{self.platform} returned non-JSON: {resp.text[:200]}") from exc

        if not isinstance(data, dict):
            return {"result": data}

        if data.get("ok") is False:
            raise AdapterError(
                f"{self.platform} API error: {data.get('description', data)}"
            )
        return data

    async def close(self) -> None:
        """Close the underlying client and rate-limiter task if owned."""
        await self._limiter.close()
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
