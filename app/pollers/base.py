"""Abstract long-polling base class."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

import httpx
from loguru import logger

from app.adapters import AbstractAdapter
from app.adapters.base import TransientError
from app.services import sync_service

# Expected (temporary) network errors that must NOT be logged as ERROR or with
# a full traceback — they are a normal part of long polling.
EXPECTED_ERRORS = (
    TransientError,
    httpx.RemoteProtocolError,
    httpx.ReadTimeout,
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.WriteError,
    httpx.PoolTimeout,
    ConnectionError,
    asyncio.TimeoutError,
)


def extract_text_edit(update: dict[str, Any]) -> tuple[str, str, str, str | None] | None:
    """Return ``(chat_id, message_id, new_text, chat_username)`` for a text edit.

    Handles both Bale/Telegram style updates (``edited_message`` /
    ``edited_channel_post``) and returns ``None`` for everything else.
    """
    for key in ("edited_message", "edited_channel_post"):
        msg = update.get(key)
        if isinstance(msg, dict) and msg.get("text"):
            chat = msg.get("chat") or {}
            chat_id = str(chat.get("id", ""))
            message_id = str(msg.get("message_id", ""))
            return chat_id, message_id, msg["text"], chat.get("username")
    return None


async def dispatch_sync_update(
    adapter: AbstractAdapter,
    session_factory: Callable,
    update: dict[str, Any],
) -> None:
    """Feed one raw update to the sync engine.

    Used by the pollers *and* by the manager bot loop (when the manager bot
    shares its token with a source listener, it is the only consumer of
    ``getUpdates`` for that bot and must also forward source-channel updates
    to the sync pipeline).
    """
    edit = extract_text_edit(update)
    if edit is not None:
        chat_id, message_id, new_text, chat_username = edit
        async with session_factory() as session:
            await sync_service.handle_edit(
                session,
                adapter.platform.value,
                chat_id,
                message_id,
                new_text,
                chat_username,
            )
        return

    for incoming in adapter.parse_update(update):
        incoming = incoming.model_copy(update={"received_at": time.perf_counter()})
        async with session_factory() as session:
            await sync_service.handle_incoming(session, adapter.platform.value, incoming)


class BasePoller(ABC):
    """Poll a platform adapter for new updates and feed them to the sync engine."""

    #: Seconds to sleep after a *poll that returned nothing*.  Platforms whose
    #: ``getUpdates`` blocks for a long-poll window (Bale) keep the default of
    #: 0; platforms with immediate responses (Rubika) must set this so the loop
    #: does not hammer the API at full speed.
    poll_interval: float = 0.0

    def __init__(
        self,
        adapter: AbstractAdapter,
        session_factory: Callable,
    ) -> None:
        self.adapter = adapter
        self._session_factory = session_factory
        self._offset: int = 0
        self._running: bool = False
        self._tasks: set[asyncio.Task] = set()
        self._consecutive_errors: int = 0

    @property
    def offset(self) -> int:
        """The last seen update offset (avoids duplicate processing)."""
        return self._offset

    @property
    def running(self) -> bool:
        """Whether the polling loop is currently active."""
        return self._running

    @abstractmethod
    async def _get_updates(self) -> list[dict[str, Any]]:
        """Fetch a batch of raw updates using long polling."""

    async def start(self) -> None:
        """Run the main polling loop until :meth:`stop` is called."""
        self._running = True
        logger.info("{} poller started", self.adapter.platform.value)
        while self._running:
            try:
                updates = await self._get_updates()
                self._consecutive_errors = 0  # reset backoff on success
                if updates:
                    for update in updates:
                        self._dispatch(update)
                elif self.poll_interval > 0:
                    # No long-poll window on this platform: pace ourselves.
                    await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                raise
            except EXPECTED_ERRORS as exc:
                self._consecutive_errors += 1
                delay = min(2 ** self._consecutive_errors, 30)
                logger.debug(
                    "{} poller: connection lost ({}); reconnecting in {}s",
                    self.adapter.platform.value,
                    type(exc).__name__,
                    delay,
                )
                await asyncio.sleep(delay)
            except Exception as exc:  # noqa: BLE001 - truly unexpected
                logger.error(
                    "{} poller unexpected error: {}: {}",
                    self.adapter.platform.value,
                    type(exc).__name__,
                    exc,
                )
                await asyncio.sleep(5)

    def _dispatch(self, update: dict[str, Any]) -> None:
        """Schedule ``update`` for processing in its own task."""
        task = asyncio.create_task(
            self._process_update(update),
            name=f"poller-{self.adapter.platform.value}-update",
        )
        self._tasks.add(task)
        task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("Update processing failed: {}", exc)

    async def stop(self) -> None:
        """Stop the polling loop cleanly and cancel in-flight updates."""
        self._running = False
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("{} poller stopped", self.adapter.platform.value)

    async def _process_update(self, update: dict[str, Any]) -> None:
        """Convert a raw update to ``IncomingMessage`` and sync it."""
        t_received = time.perf_counter()
        for incoming in self.adapter.parse_update(update):
            incoming = incoming.model_copy(update={"received_at": t_received})
            logger.debug(
                "[LATENCY] {} received msg_id={}",
                self.adapter.platform.value,
                incoming.message_id,
            )
            async with self._session_factory() as session:
                await sync_service.handle_incoming(
                    session, self.adapter.platform.value, incoming
                )
