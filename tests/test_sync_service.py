"""Tests for the synchronisation service."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from app.adapters import IncomingMessage, MessageType
from app.models import MessageLog, SyncLink
from app.queue import MemoryQueue
from app.schemas.channel import ChannelCreate
from app.services import channel_service, sync_service, user_service
from app.services.sync_service import apply_filters


# ----------------------------------------------------------------------
# Filters
# ----------------------------------------------------------------------
def _msg(text: str | None = None, mtype: MessageType = MessageType.TEXT) -> IncomingMessage:
    return IncomingMessage(message_id="1", chat_id="100", text=text, message_type=mtype)


def test_apply_filters_none() -> None:
    assert apply_filters(None, _msg("hello")) is True


def test_apply_filters_by_type() -> None:
    assert apply_filters({"message_types": ["text"]}, _msg("hello")) is True
    assert apply_filters({"message_types": ["photo"]}, _msg("hello")) is False


def test_apply_filters_by_keyword() -> None:
    assert apply_filters({"keywords": ["world"]}, _msg("hello world")) is True
    assert apply_filters({"keywords": ["missing"]}, _msg("hello world")) is False


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------
@pytest.fixture
async def user(db_session):
    return await user_service.get_or_create_user(db_session, "bale", "111", "alice")


@pytest.fixture
async def source_channel(db_session, user):
    return await channel_service.add_channel(
        db_session,
        user.id,
        ChannelCreate(platform="bale", platform_channel_id="100", title="Source", role="source"),
    )


@pytest.fixture
async def dest_channel(db_session, user):
    return await channel_service.add_channel(
        db_session,
        user.id,
        ChannelCreate(
            platform="eitaa", platform_channel_id="200", title="Dest", role="destination"
        ),
    )


@pytest.fixture
async def sync_link(db_session, user, source_channel, dest_channel):
    link = SyncLink(
        user_id=user.id,
        source_channel_id=source_channel.id,
        destination_channel_id=dest_channel.id,
        filters=None,
        is_active=True,
    )
    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(link)
    return link


# ----------------------------------------------------------------------
# handle_incoming
# ----------------------------------------------------------------------
async def test_handle_incoming_enqueues(db_session, source_channel, sync_link, monkeypatch) -> None:
    queue = MemoryQueue()
    monkeypatch.setattr(sync_service, "get_queue", lambda: queue)

    incoming = IncomingMessage(
        message_id="5", chat_id="100", text="hi", message_type=MessageType.TEXT
    )
    count = await sync_service.handle_incoming(db_session, "bale", incoming)
    assert count == 1

    job = await queue.dequeue(timeout=0.1)
    assert job is not None
    assert job["sync_link_ids"] == [sync_link.id]
    assert job["message"]["text"] == "hi"


async def test_handle_incoming_ignores_unknown_channel(db_session, monkeypatch) -> None:
    queue = MemoryQueue()
    monkeypatch.setattr(sync_service, "get_queue", lambda: queue)
    incoming = IncomingMessage(
        message_id="5", chat_id="999", text="hi", message_type=MessageType.TEXT
    )
    assert await sync_service.handle_incoming(db_session, "bale", incoming) == 0


async def test_handle_incoming_matches_source_by_username(
    db_session, user, monkeypatch
) -> None:
    """A source registered as ``@username`` must match an update with numeric id."""
    source = await channel_service.add_channel(
        db_session,
        user.id,
        ChannelCreate(
            platform="bale",
            platform_channel_id="@srcchan",
            title="srcchan",
            role="source",
        ),
    )
    dest = await channel_service.add_channel(
        db_session,
        user.id,
        ChannelCreate(
            platform="eitaa",
            platform_channel_id="@dstchan",
            role="destination",
        ),
    )
    link = SyncLink(
        user_id=user.id,
        source_channel_id=source.id,
        destination_channel_id=dest.id,
        is_active=True,
    )
    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(link)

    queue = MemoryQueue()
    monkeypatch.setattr(sync_service, "get_queue", lambda: queue)

    incoming = IncomingMessage(
        message_id="5",
        chat_id="5347185840",
        chat_username="srcchan",
        text="hi",
        message_type=MessageType.TEXT,
    )
    assert await sync_service.handle_incoming(db_session, "bale", incoming) == 1
    job = await queue.dequeue(timeout=0.1)
    assert job is not None
    assert job["sync_link_ids"] == [link.id]


async def test_handle_incoming_respects_filters(
    db_session, source_channel, sync_link, monkeypatch
) -> None:
    queue = MemoryQueue()
    monkeypatch.setattr(sync_service, "get_queue", lambda: queue)
    sync_link.filters = {"message_types": ["photo"]}
    await db_session.commit()

    incoming = IncomingMessage(
        message_id="5", chat_id="100", text="hi", message_type=MessageType.TEXT
    )
    assert await sync_service.handle_incoming(db_session, "bale", incoming) == 0


# ----------------------------------------------------------------------
# process_job
# ----------------------------------------------------------------------
class _FakeAdapter:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send_message(self, chat_id: str, text: str, **_: Any) -> str:
        self.sent.append((chat_id, text))
        return "999"


async def test_process_job_delivers_text(db_session, sync_link, monkeypatch) -> None:
    fake = _FakeAdapter()

    async def fake_adapter(session, platform, owner_id):
        return fake

    monkeypatch.setattr(sync_service, "_adapter_for", fake_adapter)

    incoming = IncomingMessage(
        message_id="5", chat_id="100", text="hi", message_type=MessageType.TEXT
    )
    job = {"message": incoming.model_dump(mode="json"), "sync_link_ids": [sync_link.id]}

    await sync_service.process_job(db_session, job)

    assert fake.sent == [("200", "hi")]

    logs = list((await db_session.execute(select(MessageLog))).scalars().all())
    assert len(logs) == 1
    assert logs[0].status == "success"
    assert logs[0].destination_message_id == "999"


async def test_process_job_delivers_parallel(db_session, user, source_channel, monkeypatch) -> None:
    d1 = await channel_service.add_channel(
        db_session, user.id,
        ChannelCreate(platform="eitaa", platform_channel_id="200", role="destination"),
    )
    d2 = await channel_service.add_channel(
        db_session, user.id,
        ChannelCreate(platform="eitaa", platform_channel_id="300", role="destination"),
    )
    l1 = SyncLink(
        user_id=user.id, source_channel_id=source_channel.id, destination_channel_id=d1.id
    )
    l2 = SyncLink(
        user_id=user.id, source_channel_id=source_channel.id, destination_channel_id=d2.id
    )
    db_session.add_all([l1, l2])
    await db_session.commit()
    await db_session.refresh(l1)
    await db_session.refresh(l2)

    fake = _FakeAdapter()

    async def fake_adapter(session, platform, owner_id):
        return fake

    monkeypatch.setattr(sync_service, "_adapter_for", fake_adapter)

    incoming = IncomingMessage(
        message_id="5", chat_id="100", text="hi", message_type=MessageType.TEXT
    )
    job = {"message": incoming.model_dump(mode="json"), "sync_link_ids": [l1.id, l2.id]}

    await sync_service.process_job(db_session, job)

    assert sorted(chat_id for chat_id, _ in fake.sent) == ["200", "300"]

    logs = list((await db_session.execute(select(MessageLog))).scalars().all())
    assert len(logs) == 2
    assert all(log.status == "success" for log in logs)


async def test_process_job_records_failure(db_session, sync_link, monkeypatch) -> None:
    class _FailingAdapter:
        async def send_message(self, chat_id, text, **_: Any) -> str:
            raise sync_service.AdapterError("boom")

    async def fake_adapter(session, platform, owner_id):
        return _FailingAdapter()

    monkeypatch.setattr(sync_service, "_adapter_for", fake_adapter)
    monkeypatch.setattr(sync_service.get_settings(), "retry_attempts", 1)

    incoming = IncomingMessage(
        message_id="5", chat_id="100", text="hi", message_type=MessageType.TEXT
    )
    job = {"message": incoming.model_dump(mode="json"), "sync_link_ids": [sync_link.id]}

    await sync_service.process_job(db_session, job)

    logs = list((await db_session.execute(select(MessageLog))).scalars().all())
    assert len(logs) == 1
    assert logs[0].status == "failed"
    assert "boom" in (logs[0].error_message or "")
