"""Synchronisation engine (event-driven, async, cache-backed).

Flow:

1. A poller receives an update and enqueues **one** job per message (carrying
   the ids of every matching sync link).
2. The worker dequeues the job and delivers to **all** destinations in parallel
   via :func:`asyncio.gather`, each destination in its own DB session.
3. Every result is recorded in ``message_logs`` and timed.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters import (
    AdapterError,
    AbstractAdapter,
    IncomingMessage,
    MessageType,
    build_adapter,
)
from app.config import get_settings
from app.database import get_session_factory
from app.models import Channel, MessageLog, SyncLink
from app.models.message_log import MessageStatus
from app.queue import get_queue
from app.services import cache_service

_MEDIA_TYPES = {
    MessageType.PHOTO,
    MessageType.VIDEO,
    MessageType.VOICE,
    MessageType.AUDIO,
    MessageType.DOCUMENT,
    MessageType.STICKER,
}

_SIGNATURE_MARKERS = ("—", "–", "🔻", "➖", "🔹", "▪️", "___", "***")

# Reused adapters (and their pooled httpx clients) per (platform, owner).
_adapter_cache: dict[tuple[str, int], AbstractAdapter] = {}


# ----------------------------------------------------------------------
# Filtering
# ----------------------------------------------------------------------
def apply_filters(filters: dict[str, Any] | None, message: IncomingMessage) -> bool:
    """Return ``True`` when ``message`` passes the configured filters."""
    if not filters:
        return True
    allowed_types = filters.get("message_types")
    if allowed_types and message.message_type.value not in allowed_types:
        return False
    keywords = filters.get("keywords")
    if keywords:
        haystack = f"{message.text or ''} {message.caption or ''}".lower()
        if not any(kw.lower() in haystack for kw in keywords):
            return False
    return True


def apply_text_transforms(
    filters: dict[str, Any] | None,
    message: IncomingMessage,
) -> IncomingMessage:
    """Apply textual transforms (e.g. signature removal) and return a copy."""
    if not filters or not message.text:
        return message
    text = message.text
    if filters.get("remove_signature"):
        lines = text.splitlines()
        while lines and _is_signature_line(lines[-1]):
            lines.pop()
        text = "\n".join(lines).strip()
    return message.model_copy(update={"text": text})


def _is_signature_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return stripped.startswith(_SIGNATURE_MARKERS) or stripped.startswith("#")


# ----------------------------------------------------------------------
# Incoming handling
# ----------------------------------------------------------------------
async def handle_incoming(
    session: AsyncSession,
    platform: str,
    incoming: IncomingMessage,
) -> int:
    """Enqueue a single job for an incoming message.

    Returns the number of destination links matched.
    """
    t_enqueued = time.perf_counter()
    source = await cache_service.get_source_channel(session, platform, incoming.chat_id)
    if source is None:
        logger.debug("No source channel for platform={} chat={}", platform, incoming.chat_id)
        return 0

    links = await cache_service.get_active_links_by_source(session, source.id)
    matching = [link for link in links if apply_filters(link.filters, incoming)]
    if not matching:
        return 0

    job = {
        "source_channel_id": source.id,
        "message": incoming.model_dump(mode="json"),
        "sync_link_ids": [link.id for link in matching],
    }
    await get_queue().enqueue(job)
    logger.info(
        "[LATENCY] enqueue {} msg_id={} links={} enqueue_ms={:.2f}",
        platform,
        incoming.message_id,
        len(matching),
        (time.perf_counter() - t_enqueued) * 1000,
    )
    return len(matching)


# ----------------------------------------------------------------------
# Job processing
# ----------------------------------------------------------------------
async def process_job(session: AsyncSession, job: dict[str, Any]) -> None:
    """Deliver a message to every destination link in parallel."""
    message = IncomingMessage.model_validate(job["message"])
    link_ids = job.get("sync_link_ids", [])

    t_start = time.perf_counter()
    links = await _load_links(session, link_ids)
    active = [link for link in links if link is not None and link.is_active]
    if not active:
        return

    semaphore = asyncio.Semaphore(max(1, get_settings().worker_concurrency))
    factory = get_session_factory()

    async def _one(link: SyncLink) -> None:
        async with semaphore:
            async with factory() as own_session:
                await _send_to_destination(own_session, link, message)

    await asyncio.gather(*[_one(link) for link in active], return_exceptions=True)

    total_ms = (time.perf_counter() - t_start) * 1000
    logger.info(
        "[LATENCY] process msg_id={} dests={} total={:.2f}ms",
        message.message_id,
        len(active),
        total_ms,
    )


async def _load_links(session: AsyncSession, link_ids: list[int]) -> list[SyncLink | None]:
    results: list[SyncLink | None] = []
    for link_id in link_ids:
        stmt = (
            select(SyncLink)
            .where(SyncLink.id == link_id)
            .options(
                selectinload(SyncLink.source_channel),
                selectinload(SyncLink.destination_channel),
            )
        )
        results.append((await session.execute(stmt)).scalars().first())
    return results


async def _send_to_destination(
    session: AsyncSession,
    link: SyncLink,
    message: IncomingMessage,
) -> None:
    """Deliver one message to one destination and record the outcome."""
    source_channel = link.source_channel
    dest_channel = link.destination_channel
    owner_user_id = link.user_id

    source_adapter = await _adapter_for(session, source_channel.platform, owner_user_id)
    dest_adapter = await _adapter_for(session, dest_channel.platform, owner_user_id)

    log = MessageLog(
        sync_link_id=link.id,
        source_message_id=message.message_id,
        status=MessageStatus.PENDING,
    )
    session.add(log)
    await session.commit()

    t_http = time.perf_counter()
    try:
        destination_id = await _with_retry(
            _deliver,
            source_channel,
            dest_channel,
            source_adapter,
            dest_adapter,
            link.filters,
            message,
        )
        log.destination_message_id = destination_id
        log.status = MessageStatus.SUCCESS
        logger.info(
            "[LATENCY] synced link={} src_msg={} -> dst_msg={} ({}) {}ms",
            link.id,
            message.message_id,
            destination_id,
            dest_channel.platform,
            (time.perf_counter() - t_http) * 1000,
        )
    except AdapterError as exc:
        log.status = MessageStatus.FAILED
        log.error_message = str(exc)
        logger.error("Sync failed for link {}: {}", link.id, exc)
    await session.commit()


async def _with_retry(coro_factory, *args, **kwargs) -> str:
    """Call ``coro_factory(*args, **kwargs)`` with exponential backoff retries."""
    settings = get_settings()
    last_exc: AdapterError | None = None
    for attempt in range(settings.retry_attempts):
        try:
            return await coro_factory(*args, **kwargs)
        except AdapterError as exc:
            last_exc = exc
            if attempt == settings.retry_attempts - 1:
                break
            delay = settings.retry_backoff_base ** attempt
            logger.warning(
                "Retry {}/{} after error: {}",
                attempt + 1,
                settings.retry_attempts,
                exc,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


async def _deliver(
    source_channel: Channel,
    dest_channel: Channel,
    source_adapter: AbstractAdapter,
    dest_adapter: AbstractAdapter,
    filters: dict[str, Any] | None,
    message: IncomingMessage,
) -> str:
    """Deliver one message using the right copy strategy."""
    dest_chat_id = dest_channel.platform_channel_id
    message = apply_text_transforms(filters, message)

    msg_type = message.message_type
    reply_markup = message.reply_markup

    can_copy = (
        source_channel.platform == dest_channel.platform
        and dest_adapter.supports_copy_message
        and not message.is_forwarded
    )

    if msg_type == MessageType.TEXT:
        return await dest_adapter.send_message(
            dest_chat_id,
            message.text or "",
            parse_mode=message.parse_mode,
            reply_markup=reply_markup,
        )

    if msg_type in _MEDIA_TYPES:
        if can_copy:
            return await dest_adapter.copy_message(
                source_channel.platform_channel_id,
                dest_chat_id,
                message.message_id,
                caption=message.caption,
                reply_markup=reply_markup,
            )
        file_bytes = await source_adapter.download_file(message.file_id or "")
        return await _send_media(dest_adapter, dest_chat_id, message, file_bytes)

    if msg_type == MessageType.LOCATION and message.location:
        return await dest_adapter.send_location(
            dest_chat_id,
            message.location["latitude"],
            message.location["longitude"],
            reply_markup=reply_markup,
        )

    if msg_type == MessageType.POLL and message.poll:
        question = message.poll.get("question", "")
        options = [o.get("text", "") for o in message.poll.get("options", [])]
        return await dest_adapter.send_poll(dest_chat_id, question, options)

    if message.text:
        return await dest_adapter.send_message(
            dest_chat_id,
            message.text,
            parse_mode=message.parse_mode,
            reply_markup=reply_markup,
        )

    raise AdapterError(f"Unsupported message type for sync: {msg_type}")


async def _send_media(
    dest_adapter: AbstractAdapter,
    chat_id: str,
    message: IncomingMessage,
    file_bytes: bytes,
) -> str:
    """Upload ``file_bytes`` to the destination using the right media method."""
    caption = message.caption
    parse_mode = message.parse_mode
    reply_markup = message.reply_markup

    if message.message_type == MessageType.PHOTO:
        return await dest_adapter.send_photo(
            chat_id, file_bytes, caption=caption, parse_mode=parse_mode, reply_markup=reply_markup
        )
    if message.message_type == MessageType.VIDEO:
        return await dest_adapter.send_video(
            chat_id, file_bytes, caption=caption, parse_mode=parse_mode, reply_markup=reply_markup
        )
    if message.message_type == MessageType.VOICE:
        return await dest_adapter.send_voice(chat_id, file_bytes, caption=caption, reply_markup=reply_markup)
    if message.message_type == MessageType.AUDIO:
        return await dest_adapter.send_document(
            chat_id,
            file_bytes,
            filename=message.file_name or "audio",
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    if message.message_type == MessageType.DOCUMENT:
        return await dest_adapter.send_document(
            chat_id,
            file_bytes,
            filename=message.file_name,
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    if message.message_type == MessageType.STICKER:
        return await dest_adapter.send_sticker(chat_id, file_bytes)
    raise AdapterError(f"Unsupported media type: {message.message_type}")


async def _adapter_for(
    session: AsyncSession, platform: str, owner_user_id: int
) -> AbstractAdapter:
    """Return a cached adapter (with its pooled HTTP client) for a platform/owner."""
    key = (platform, owner_user_id)
    adapter = _adapter_cache.get(key)
    if adapter is not None:
        return adapter
    token = await cache_service.get_bot_token(session, platform, owner_user_id)
    adapter = build_adapter(platform, token)
    _adapter_cache[key] = adapter
    return adapter


# ----------------------------------------------------------------------
# Edit / delete propagation
# ----------------------------------------------------------------------
async def handle_delete(
    session: AsyncSession,
    platform: str,
    chat_id: str,
    message_id: str,
) -> int:
    """Delete the destination copies of a deleted source message."""
    source = await cache_service.get_source_channel(session, platform, chat_id)
    if source is None:
        return 0
    logs = await _logs_for_source_message(session, source.id, message_id)
    deleted = 0
    for log in logs:
        if log.destination_message_id is None:
            continue
        link = log.sync_link
        try:
            adapter = await _adapter_for(session, link.destination_channel.platform, link.user_id)
            await adapter.delete_message(
                link.destination_channel.platform_channel_id,
                log.destination_message_id,
            )
            deleted += 1
        except AdapterError as exc:
            logger.warning("Delete propagation failed: {}", exc)
    return deleted


async def handle_edit(
    session: AsyncSession,
    platform: str,
    chat_id: str,
    message_id: str,
    new_text: str,
) -> int:
    """Edit the destination copies of an edited source text message."""
    source = await cache_service.get_source_channel(session, platform, chat_id)
    if source is None:
        return 0
    logs = await _logs_for_source_message(session, source.id, message_id)
    edited = 0
    for log in logs:
        if log.destination_message_id is None:
            continue
        link = log.sync_link
        try:
            adapter = await _adapter_for(session, link.destination_channel.platform, link.user_id)
            await adapter.edit_message_text(
                link.destination_channel.platform_channel_id,
                log.destination_message_id,
                new_text,
            )
            edited += 1
        except AdapterError as exc:
            logger.warning("Edit propagation failed: {}", exc)
    return edited


async def _logs_for_source_message(
    session: AsyncSession,
    source_channel_id: int,
    source_message_id: str,
) -> list[MessageLog]:
    stmt = (
        select(MessageLog)
        .join(SyncLink, SyncLink.id == MessageLog.sync_link_id)
        .where(
            SyncLink.source_channel_id == source_channel_id,
            MessageLog.source_message_id == source_message_id,
            MessageLog.status == MessageStatus.SUCCESS,
        )
        .options(
            selectinload(MessageLog.sync_link).selectinload(SyncLink.destination_channel),
        )
    )
    return list((await session.execute(stmt)).scalars().all())
