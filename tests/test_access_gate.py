"""Tests for the ``/RSAsecret`` access gate on the manager bot.

The manager UI must be invisible until the user sends the secret command.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app import anon_bridge
from app.adapters import BaleAdapter
from app.bot_manager import handlers
from app.bot_manager import keyboards as kb
from app.bot_manager.states import state_machine
from app.config import get_settings
from app.services import access_service


class FakeBaleAPI:
    """Minimal Bale API that only records what was sent."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.answered: list[str] = []
        self._message_id = 1000
        self._update_id = 0

    def text_update(self, text: str, user_id: int = 111) -> dict:
        self._update_id += 1
        self._message_id += 1
        return {
            "update_id": self._update_id,
            "message": {
                "message_id": self._message_id,
                "chat": {"id": user_id, "type": "private"},
                "from": {"id": user_id, "first_name": "Tester"},
                "text": text,
            },
        }

    def callback_update(self, data: str, user_id: int = 111) -> dict:
        self._update_id += 1
        self._message_id += 1
        return {
            "update_id": self._update_id,
            "callback_query": {
                "id": "cb-1",
                "from": {"id": user_id, "first_name": "Tester"},
                "message": {
                    "message_id": self._message_id,
                    "chat": {"id": user_id, "type": "private"},
                },
                "data": data,
            },
        }

    def handler(self, request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        if method == "answerCallbackQuery":
            self.answered.append(json.loads(request.content)["callback_query_id"])
            return httpx.Response(200, json={"ok": True, "result": True})
        if method == "sendMessage":
            self.sent.append(json.loads(request.content))
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
        return httpx.Response(404, json={"ok": False, "description": method})


@pytest.fixture
def fake_api():
    return FakeBaleAPI()


@pytest.fixture
async def adapter(fake_api):
    client = httpx.AsyncClient(transport=httpx.MockTransport(fake_api.handler))
    adapter = BaleAdapter("TOKEN", client=client)
    try:
        yield adapter
    finally:
        await adapter.close()
        await client.aclose()


@pytest.fixture
def clean_states():
    state_machine._users.clear()
    yield
    state_machine._users.clear()


@pytest.fixture
def gate_on(monkeypatch):
    """Enable the gate with the default secret."""
    monkeypatch.setattr(get_settings(), "manager_access_secret", "RSAsecret")


async def drive(db_session, adapter, update):
    await handlers.handle_update(db_session, adapter, "bale", update)


async def test_unauthorized_user_sees_nothing(
    db_session, fake_api, adapter, clean_states, gate_on
):
    await drive(db_session, adapter, fake_api.text_update("/mychannels"))
    assert fake_api.sent == []

    await drive(db_session, adapter, fake_api.callback_update(kb.CMD_ADDCHANNEL))
    assert fake_api.sent == []
    assert fake_api.answered == []


async def test_public_start_shows_anonymous_intro(
    db_session, fake_api, adapter, clean_states, gate_on
):
    """/start is public: it shows the anonymous-bot intro to everyone."""
    await drive(db_session, adapter, fake_api.text_update("/start"))
    assert len(fake_api.sent) == 1
    msg = fake_api.sent[-1]
    assert msg["text"] == handlers.PUBLIC_START_TEXT
    buttons = [
        btn for row in msg["reply_markup"]["inline_keyboard"] for btn in row
    ]
    assert buttons[0]["text"] == "🔗 لینک ناشناس"
    assert buttons[0]["callback_data"] == anon_bridge.ANON_PANEL


async def test_secret_unlocks_the_bot(
    db_session, fake_api, adapter, clean_states, gate_on
):
    await drive(db_session, adapter, fake_api.text_update("/RSAsecret"))
    assert len(fake_api.sent) == 1
    datas = [
        btn.get("callback_data")
        for row in fake_api.sent[-1]["reply_markup"]["inline_keyboard"]
        for btn in row
    ]
    assert kb.CMD_ADDCHANNEL in datas

    # The normal UI is reachable after unlocking.
    await drive(db_session, adapter, fake_api.text_update("/mychannels"))
    assert len(fake_api.sent) == 2


async def test_wrong_secret_shows_nothing(
    db_session, fake_api, adapter, clean_states, gate_on
):
    await drive(db_session, adapter, fake_api.text_update("/RSAsecret nope"))
    assert fake_api.sent == []


async def test_custom_secret_requires_the_value(
    db_session, fake_api, adapter, clean_states, monkeypatch
):
    monkeypatch.setattr(get_settings(), "manager_access_secret", "s3cr3t")

    await drive(db_session, adapter, fake_api.text_update("/RSAsecret"))
    assert fake_api.sent == []

    await drive(db_session, adapter, fake_api.text_update("/RSAsecret s3cr3t"))
    assert len(fake_api.sent) == 1


async def test_grant_persists_across_lookups(db_session, gate_on):
    assert await access_service.is_authorized(db_session, "bale", "777") is False
    await access_service.grant_access(db_session, "bale", "777")
    assert await access_service.is_authorized(db_session, "bale", "777") is True
    # Idempotent.
    await access_service.grant_access(db_session, "bale", "777")
    assert await access_service.is_authorized(db_session, "bale", "777") is True


async def test_empty_secret_disables_the_gate(
    db_session, fake_api, adapter, clean_states, monkeypatch
):
    monkeypatch.setattr(get_settings(), "manager_access_secret", "")
    await drive(db_session, adapter, fake_api.text_update("/mychannels"))
    assert len(fake_api.sent) == 1


# ----------------------------------------------------------------------
# Routing: anonymous flows are public, sync flows are gated
# ----------------------------------------------------------------------
@pytest.fixture
def anon_spy(monkeypatch):
    calls = {"message": [], "callback": []}

    async def fake_message(chat_id, user_id, text, msg):
        calls["message"].append((user_id, text))

    async def fake_callback(data, callback_id, user_id, message_id, chat_id):
        calls["callback"].append(data)

    monkeypatch.setattr(anon_bridge, "handle_message", fake_message)
    monkeypatch.setattr(anon_bridge, "handle_callback", fake_callback)
    return calls


async def test_plain_text_goes_to_anon(
    db_session, fake_api, adapter, clean_states, gate_on, anon_spy
):
    await drive(db_session, adapter, fake_api.text_update("سلام"))
    assert anon_spy["message"] == [("111", "سلام")]
    assert fake_api.sent == []


async def test_start_deeplink_goes_to_anon(
    db_session, fake_api, adapter, clean_states, gate_on, anon_spy
):
    await drive(db_session, adapter, fake_api.text_update("/start anon_ABC123"))
    assert anon_spy["message"] == [("111", "/start anon_ABC123")]


async def test_anon_callback_is_public(
    db_session, fake_api, adapter, clean_states, gate_on, anon_spy
):
    await drive(db_session, adapter, fake_api.callback_update("anol_list"))
    assert anon_spy["callback"] == ["anol_list"]


async def test_anon_panel_button_opens_panel(
    db_session, fake_api, adapter, clean_states, gate_on, anon_spy
):
    await drive(db_session, adapter, fake_api.callback_update(anon_bridge.ANON_PANEL))
    assert anon_spy["callback"] == [anon_bridge.ANON_PANEL]


async def test_unauthorized_sync_command_not_forwarded(
    db_session, fake_api, adapter, clean_states, gate_on, anon_spy
):
    await drive(db_session, adapter, fake_api.text_update("/addchannel"))
    assert anon_spy["message"] == []
    assert fake_api.sent == []
