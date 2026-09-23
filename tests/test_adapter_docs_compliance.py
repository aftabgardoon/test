"""Documentation-compliance tests for the platform adapters.

Each test encodes a requirement taken from the official docs:

* **Bale** (https://docs.bale.ai): ``getUpdates`` accepts only
  ``offset``/``limit``/``timeout``; methods have no ``parse_mode`` parameter
  (Bale text is always Markdown); unexpected/``null`` parameters must not be
  sent (``copyMessage`` takes exactly ``chat_id``/``from_chat_id``/
  ``message_id``; an inline button may carry only one optional field).
* **Rubika** (https://rubika.ir/botapi): file uploads go to ``upload_url`` as
  ``multipart/form-data`` with a field named ``file``; ``UpdatedMessage`` /
  ``RemovedMessage`` updates must not be re-posted as new messages; media
  messages carry their caption in ``text`` alongside ``file``.
* **Eitaa** (https://eitaayar.ir/api): only ``getMe``/``sendMessage``/
  ``sendFile`` exist (no ``sendPoll``).
"""

from __future__ import annotations

import asyncio
import json
from contextlib import nullcontext
from typing import Any

import httpx
import pytest

from app.adapters import BaleAdapter, EitaaAdapter, Platform, RubikaAdapter
from app.adapters.base import MessageType
from app.config import get_settings
from app.pollers import BalePoller, RubikaPoller
from app.services import sync_service


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _close(*adapters_and_clients: Any) -> None:
    for obj in adapters_and_clients:
        if hasattr(obj, "close"):
            await obj.close()
        elif hasattr(obj, "aclose"):
            await obj.aclose()


# ----------------------------------------------------------------------
# Bale
# ----------------------------------------------------------------------
async def test_bale_send_message_drops_parse_mode_and_nulls():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    adapter = BaleAdapter("T", client=_mock_client(handler))
    try:
        from app.adapters import InlineKeyboardButton, InlineKeyboardMarkup

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="A", callback_data="a")],
                [InlineKeyboardButton(text="B", url="https://example.com")],
            ]
        )
        await adapter.send_message("1", "hi", parse_mode="HTML", reply_markup=markup)
    finally:
        await _close(adapter)

    payload = captured["json"]
    assert "parse_mode" not in payload  # undocumented for Bale
    rows = payload["reply_markup"]["inline_keyboard"]
    assert rows[0][0] == {"text": "A", "callback_data": "a"}  # no url: null
    assert rows[1][0] == {"text": "B", "url": "https://example.com"}  # no callback_data: null


async def test_bale_copy_message_sends_only_documented_params():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 9}})

    adapter = BaleAdapter("T", client=_mock_client(handler))
    try:
        # Even when the caller passes caption/reply_markup, Bale's
        # documented copyMessage must receive exactly the 3 params.
        from app.adapters import InlineKeyboardButton, InlineKeyboardMarkup

        markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="A", callback_data="a")]]
        )
        await adapter.copy_message(
            "from-chat", "to-chat", "42", caption="cap", reply_markup=markup
        )
    finally:
        await _close(adapter)

    assert captured["json"] == {
        "chat_id": "to-chat",
        "from_chat_id": "from-chat",
        "message_id": "42",
    }


async def test_bale_get_updates_never_sends_allowed_updates():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"ok": True, "result": []})

    adapter = BaleAdapter("T", client=_mock_client(handler))
    try:
        await adapter.get_raw_updates(offset=5, timeout=15, allowed_updates=["message"])
    finally:
        await _close(adapter)

    assert "allowed_updates" not in captured["params"]
    assert captured["params"]["offset"] == "5"
    assert captured["params"]["timeout"] == "15"


# ----------------------------------------------------------------------
# Rubika
# ----------------------------------------------------------------------
def test_rubika_parse_media_message_keeps_caption():
    adapter = RubikaAdapter("T")
    msg = adapter._parse_message(
        "chat1",
        {
            "message_id": "m1",
            "sender_id": "u1",
            "text": "عکس جدید",  # caption carried in text for media messages
            "file": {"file_id": "f1", "file_name": "photo.jpg", "size": "100"},
        },
    )
    assert msg.message_type == MessageType.PHOTO
    assert msg.file_id == "f1"
    assert msg.caption == "عکس جدید"
    assert msg.text is None  # must not be treated as a text message


def test_rubika_parse_plain_text_still_text():
    adapter = RubikaAdapter("T")
    msg = adapter._parse_message("chat1", {"message_id": "m2", "text": "سلام"})
    assert msg.message_type == MessageType.TEXT
    assert msg.text == "سلام"
    assert msg.caption is None


def test_rubika_parse_update_ignores_edits_and_deletions():
    adapter = RubikaAdapter("T")
    edited = {
        "type": "UpdatedMessage",
        "chat_id": "c1",
        "updated_message": {"message_id": "5", "text": "edited"},
    }
    removed = {"type": "RemovedMessage", "chat_id": "c1", "removed_message_id": "5"}
    assert adapter.parse_update(edited) == []
    assert adapter.parse_update(removed) == []


async def test_rubika_file_upload_is_multipart():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/requestSendFile"):
            return httpx.Response(200, json={"upload_url": "https://upload.example/up"})
        if request.url.host == "upload.example":
            captured["content_type"] = request.headers.get("content-type", "")
            captured["body"] = request.content
            return httpx.Response(200, json={"file_id": "f-123"})
        if path.endswith("/sendFile"):
            captured["json"] = json.loads(request.content)
            return httpx.Response(200, json={"message_id": "m-9"})
        raise AssertionError(f"unexpected request: {request.url}")

    adapter = RubikaAdapter("T", client=_mock_client(handler))
    try:
        mid = await adapter.send_photo("chat9", b"IMGDATA", caption="عکس")
    finally:
        await _close(adapter)

    assert mid == "m-9"
    assert captured["content_type"].startswith("multipart/form-data")
    assert b'name="file"' in captured["body"]
    assert b"IMGDATA" in captured["body"]
    assert captured["json"] == {"chat_id": "chat9", "file_id": "f-123", "text": "عکس"}


# ----------------------------------------------------------------------
# Rubika poller: edit / delete propagation + pacing
# ----------------------------------------------------------------------
class _FakeRubikaAdapter:
    platform = Platform.RUBIKA

    def __init__(self, updates: list[dict] | None = None) -> None:
        self._updates = list(updates or [])
        self.calls = 0

    async def get_updates_raw(self, offset_id=None, limit=100):
        self.calls += 1
        updates = self._updates[:1]
        if updates:
            self._updates = self._updates[1:]
        return updates, "next-1"

    def parse_update(self, update: dict) -> list:
        return []


async def test_rubika_poller_routes_edit_to_handle_edit(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_handle_edit(session, platform, chat_id, message_id, new_text):
        captured.update(
            platform=platform, chat_id=chat_id, message_id=message_id, new_text=new_text
        )
        return 1

    monkeypatch.setattr(sync_service, "handle_edit", fake_handle_edit)

    adapter = _FakeRubikaAdapter(
        [
            {
                "type": "UpdatedMessage",
                "chat_id": "c1",
                "updated_message": {"message_id": "55", "text": "new"},
            }
        ]
    )
    poller = RubikaPoller(adapter, lambda: nullcontext(None))
    await poller._process_update(adapter._updates[0])

    assert captured == {
        "platform": "rubika", "chat_id": "c1", "message_id": "55", "new_text": "new"
    }


async def test_rubika_poller_routes_delete_to_handle_delete(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_handle_delete(session, platform, chat_id, message_id):
        captured.update(platform=platform, chat_id=chat_id, message_id=message_id)
        return 1

    monkeypatch.setattr(sync_service, "handle_delete", fake_handle_delete)

    adapter = _FakeRubikaAdapter(
        [{"type": "RemovedMessage", "chat_id": "c2", "removed_message_id": "77"}]
    )
    poller = RubikaPoller(adapter, lambda: nullcontext(None))
    await poller._process_update(adapter._updates[0])

    assert captured == {"platform": "rubika", "chat_id": "c2", "message_id": "77"}


async def test_rubika_poller_paces_empty_polls(monkeypatch):
    """Rubika getUpdates returns immediately; the loop must sleep, not spin."""
    adapter = _FakeRubikaAdapter([])
    poller = RubikaPoller(adapter, lambda: nullcontext(None))
    assert poller.poll_interval == get_settings().polling_interval > 0

    delays: list[float] = []

    async def fake_sleep(delay):
        delays.append(delay)
        if adapter.calls >= 3:
            poller._running = False

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    try:
        await poller.start()
    finally:
        monkeypatch.undo()

    assert adapter.calls >= 3
    assert delays and all(d == poller.poll_interval for d in delays)


def test_bale_poller_has_no_idle_sleep():
    """Bale long-polling already blocks; no extra idle sleep is expected."""
    adapter = _FakeRubikaAdapter([])
    adapter.platform = Platform.BALE
    poller = BalePoller(adapter, lambda: nullcontext(None))
    assert poller.poll_interval == 0


# ----------------------------------------------------------------------
# Eitaa
# ----------------------------------------------------------------------
async def test_eitaa_poll_is_rendered_as_text():
    """Eitaa has no sendPoll method (docs: getMe/sendMessage/sendFile only)."""
    from urllib.parse import parse_qs

    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["form"] = parse_qs(request.content.decode())
        return httpx.Response(200, json={"ok": True, "result": {"message_id": "85"}})

    adapter = EitaaAdapter("T", client=_mock_client(handler))
    try:
        mid = await adapter.send_poll("chat1", "رأی‌گیری؟", ["بله", "نه"])
    finally:
        await _close(adapter)

    assert mid == "85"
    assert captured["url"].endswith("/api/T/sendMessage")
    assert "sendPoll" not in captured["url"]
    text = captured["form"]["text"][0]
    assert text == "رأی‌گیری؟\n1. بله\n2. نه"


async def test_eitaa_message_id_extraction_rejects_garbage():
    from app.adapters.base import AdapterError

    adapter = EitaaAdapter("T")
    resp = httpx.Response(200, json={"ok": True, "result": {}})
    with pytest.raises(AdapterError):
        adapter._extract_message_id(resp)

    resp_ok = httpx.Response(200, json={"ok": True, "result": {"message_id": 123}})
    assert adapter._extract_message_id(resp_ok) == "123"


async def test_eitaa_strips_at_sign_from_chat_id():
    """Eitaa expects ``chat_id`` without a leading ``@`` (docs: chat_id=eitaa)."""
    from urllib.parse import parse_qs

    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["form"] = parse_qs(request.content.decode())
        return httpx.Response(200, json={"ok": True, "result": {"message_id": "9"}})

    adapter = EitaaAdapter("T", client=_mock_client(handler))
    try:
        await adapter.send_message("@aftabgardoon_com", "hi")
    finally:
        await _close(adapter)

    assert captured["form"]["chat_id"][0] == "aftabgardoon_com"


# ----------------------------------------------------------------------
# Post-audit hardening tests
# ----------------------------------------------------------------------
def test_bale_parse_update_ignores_edited_content():
    """Edited Bale messages must not be re-emitted as new messages.

    Text edits are routed to edit propagation by the poller / manager loop;
    non-text edits (e.g. a changed photo caption) would otherwise be
    duplicated in destination channels.
    """
    adapter = BaleAdapter("T")
    edited_photo = {
        "update_id": 5,
        "edited_channel_post": {
            "message_id": "42",
            "chat": {"id": "500"},
            "photo": [{"file_id": "abc"}],
            "caption": "new caption",
        },
    }
    assert adapter.parse_update(edited_photo) == []

    edited_text = {
        "update_id": 6,
        "edited_message": {
            "message_id": "43",
            "chat": {"id": "111"},
            "text": "edited",
        },
    }
    assert adapter.parse_update(edited_text) == []

    # New content is still parsed.
    new_post = {
        "update_id": 7,
        "channel_post": {
            "message_id": "44",
            "chat": {"id": "500"},
            "text": "fresh",
        },
    }
    parsed = adapter.parse_update(new_post)
    assert len(parsed) == 1
    assert parsed[0].text == "fresh"


def test_platform_supports_source_flags():
    from app.adapters import platform_supports_source

    assert platform_supports_source("bale") is True
    assert platform_supports_source("rubika") is True
    assert platform_supports_source("eitaa") is False
    assert platform_supports_source(Platform.BALE) is True
    assert platform_supports_source("nope") is False


# ----------------------------------------------------------------------
# Post-docs-audit fixes: copyMessage purity, poll option shapes, audio
# ----------------------------------------------------------------------
async def test_bale_send_audio_uses_documented_method():
    """Bale has sendAudio (mp3/m4a, music player) — use it, not sendDocument."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.url.path.rsplit("/", 1)[-1]
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 3}})

    adapter = BaleAdapter("T", client=_mock_client(handler))
    try:
        await adapter.send_audio("1", "fid123", caption="hi")
    finally:
        await _close(adapter)

    assert captured["method"] == "sendAudio"
    assert captured["json"]["audio"] == "fid123"
    assert captured["json"]["caption"] == "hi"
    assert "parse_mode" not in captured["json"]


async def test_rubika_send_audio_uses_music_file_type():
    """Rubika FileTypeEnum: Music (mp3) — not the generic File type."""
    calls: list[tuple] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = str(request.url.path)
        if path.endswith("/requestSendFile"):
            calls.append(("request", json.loads(request.content)))
            return httpx.Response(200, json={"upload_url": "http://up.local/f", "file_id": "F1"})
        if "up.local" in str(request.url):
            calls.append(("upload", None))
            return httpx.Response(200, json={})
        if path.endswith("/sendFile"):
            calls.append(("send", json.loads(request.content)))
            return httpx.Response(200, json={"message_id": "9"})
        return httpx.Response(404, json={})

    adapter = RubikaAdapter("T", client=_mock_client(handler))
    try:
        await adapter.send_audio("10", b"mp3-bytes", filename="song.mp3", caption="c")
    finally:
        await _close(adapter)

    assert calls[0] == ("request", {"type": "Music"})
    assert ("upload", None) in calls
    assert calls[-1][0] == "send"
    assert calls[-1][1]["file_id"] == "F1"
    assert calls[-1][1]["chat_id"] == "10"


async def test_deliver_handles_rubika_string_poll_options():
    """Rubika Poll.options is list[string]; Bale/Telegram-style is list of dicts.

    The old code did o.get("text") on every option, which raised
    AttributeError (and silently dropped the sync) for Rubika string options.
    """
    from app.adapters.base import IncomingMessage
    from app.models import Channel
    from app.models.channel import ChannelRole

    class _FakeDest:
        supports_copy_message = False

        def __init__(self) -> None:
            self.polls: list[tuple] = []

        async def send_poll(self, chat_id, question, options):
            self.polls.append((chat_id, question, options))
            return "77"

    src = Channel(platform="rubika", platform_channel_id="s1", role=ChannelRole.SOURCE)
    dst = Channel(platform="rubika", platform_channel_id="d1", role=ChannelRole.DESTINATION)

    # Rubika shape: plain strings
    msg = IncomingMessage(
        message_id="5",
        chat_id="s1",
        message_type=MessageType.POLL,
        poll={"question": "Q?", "options": ["yes", "no"]},
    )
    dest = _FakeDest()
    mid = await sync_service._deliver(src, dst, None, dest, None, msg)
    assert mid == "77"
    assert dest.polls == [("d1", "Q?", ["yes", "no"])]

    # Bale/Telegram shape: dicts with a text key
    msg2 = IncomingMessage(
        message_id="6",
        chat_id="s1",
        message_type=MessageType.POLL,
        poll={"question": "Q2?", "options": [{"text": "a"}, {"text": "b"}]},
    )
    mid2 = await sync_service._deliver(src, dst, None, dest, None, msg2)
    assert mid2 == "77"
    assert dest.polls[-1] == ("d1", "Q2?", ["a", "b"])
