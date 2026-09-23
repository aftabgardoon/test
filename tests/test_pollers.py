"""Tests for the long-polling pollers."""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from typing import Any

from app.adapters import EitaaAdapter, IncomingMessage, MessageType, Platform
from app.pollers import BalePoller, build_polling_adapters, start_all_pollers
from app.pollers.bale_poller import _extract_edit
from app.services import sync_service


class _FakeBaleAdapter:
    platform = Platform.BALE

    def __init__(self, batches: list[list[dict[str, Any]]] | None = None) -> None:
        self._batches = list(batches or [])
        self.calls: list[dict[str, Any]] = []

    async def get_raw_updates(
        self,
        offset: int | None = None,
        timeout: int = 30,
        allowed_updates: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {"offset": offset, "timeout": timeout, "allowed_updates": allowed_updates}
        )
        return self._batches.pop(0) if self._batches else []

    def parse_update(self, update: dict[str, Any]) -> list[IncomingMessage]:
        msg = update.get("message") or {}
        return [
            IncomingMessage(
                message_id=str(msg.get("message_id", "0")),
                chat_id=str((msg.get("chat") or {}).get("id", "")),
                text=msg.get("text"),
                message_type=MessageType.TEXT,
            )
        ]


def test_extract_edit() -> None:
    edit = {"edited_message": {"message_id": 5, "chat": {"id": 9}, "text": "x"}}
    assert _extract_edit(edit) == ("9", "5", "x", None)
    edit_named = {
        "edited_message": {
            "message_id": 5,
            "chat": {"id": 9, "username": "chan"},
            "text": "x",
        }
    }
    assert _extract_edit(edit_named) == ("9", "5", "x", "chan")
    normal = {"message": {"message_id": 5, "chat": {"id": 9}, "text": "x"}}
    assert _extract_edit(normal) is None


async def test_bale_poller_advances_offset() -> None:
    adapter = _FakeBaleAdapter(
        [[{"update_id": 7, "message": {"message_id": 5, "chat": {"id": 100}, "text": "hi"}}]]
    )
    poller = BalePoller(adapter, lambda: nullcontext(None))

    updates = await poller._get_updates()

    assert len(updates) == 1
    assert poller.offset == 8
    assert adapter.calls[0]["offset"] is None  # first call has no offset
    assert adapter.calls[0]["timeout"] == 15
    # Bale's documented getUpdates has no allowed_updates parameter; sending
    # it risks a 400 that breaks the whole poller, so it must never be sent.
    assert adapter.calls[0]["allowed_updates"] is None


async def test_bale_poller_process_update(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_handle_incoming(session, platform, incoming):
        captured["platform"] = platform
        captured["incoming"] = incoming
        return 1

    monkeypatch.setattr(sync_service, "handle_incoming", fake_handle_incoming)

    adapter = _FakeBaleAdapter()
    poller = BalePoller(adapter, lambda: nullcontext(None))
    update = {"update_id": 1, "message": {"message_id": 5, "chat": {"id": 100}, "text": "hi"}}

    await poller._process_update(update)

    assert captured["platform"] == "bale"
    assert captured["incoming"].text == "hi"


async def test_bale_poller_handles_edit(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_handle_edit(
        session, platform, chat_id, message_id, new_text, chat_username=None
    ):
        captured.update(chat_id=chat_id, message_id=message_id, new_text=new_text)
        return 1

    monkeypatch.setattr(sync_service, "handle_edit", fake_handle_edit)

    adapter = _FakeBaleAdapter()
    poller = BalePoller(adapter, lambda: nullcontext(None))
    update = {
        "update_id": 1,
        "edited_message": {"message_id": 5, "chat": {"id": 100}, "text": "edited"},
    }

    await poller._process_update(update)

    assert captured == {"chat_id": "100", "message_id": "5", "new_text": "edited"}


def test_start_all_pollers_skips_destination_only() -> None:
    eitaa = EitaaAdapter("t")
    tasks = asyncio.run(start_all_pollers({Platform.EITAA: eitaa}, lambda: nullcontext(None)))
    assert tasks == []


def test_build_polling_adapters_empty_without_tokens() -> None:
    assert build_polling_adapters() == {}
