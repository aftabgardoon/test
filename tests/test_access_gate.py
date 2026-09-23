"""Tests for the ``/RSAsecret`` access gate on the manager bot.

The manager UI must be invisible until the user sends the secret command.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

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
    await drive(db_session, adapter, fake_api.text_update("/start"))
    assert fake_api.sent == []

    await drive(db_session, adapter, fake_api.callback_update(kb.CMD_ADDCHANNEL))
    assert fake_api.sent == []
    assert fake_api.answered == []


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

    # Now the normal UI is reachable.
    await drive(db_session, adapter, fake_api.text_update("/start"))
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
    await drive(db_session, adapter, fake_api.text_update("/start"))
    assert len(fake_api.sent) == 1
