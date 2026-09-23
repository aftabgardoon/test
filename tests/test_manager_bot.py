"""End-to-end tests for the manager bot (Bale) button flows.

These tests drive :func:`app.bot_manager.handlers.handle_update` with raw
Bale-style updates against a mocked Bale HTTP API (``httpx.MockTransport``).
They reproduce the exact button conversations users perform with the admin
bot and assert that every button works — including the ones that were broken
by the ``cache_service`` module/instance bug:

* ``/setsource`` → channel button (source selection)
* ``/adddest``   → source button + destination button (link creation)
* ``/pause``     → link toggle button

They also cover the Bale-docs requirement that ``answerCallbackQuery`` must
never prevent a button from being processed (old clients whose
``callback_query_id`` starts with ``"1"`` do not support the feature).
"""

from __future__ import annotations

import json
from contextlib import nullcontext
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.adapters import BaleAdapter
from app.bot_manager import handlers
from app.bot_manager import keyboards as kb
from app.bot_manager.states import States, state_machine
from app.models import Channel, SyncLink
from app.models.channel import ChannelRole
from app.schemas.channel import ChannelCreate
from app.services import channel_service
from app.utils.logger import setup_logger

setup_logger()


# ----------------------------------------------------------------------
# Fake Bale API
# ----------------------------------------------------------------------
class FakeBaleAPI:
    """Minimal in-memory implementation of the Bale bot HTTP API."""

    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []
        self.sent: list[dict[str, Any]] = []
        self.answered: list[str] = []
        self.fail_answer = False
        self._update_id = 0
        self._message_id = 1000

    # -- update generation -------------------------------------------------
    def _next_update_id(self) -> int:
        self._update_id += 1
        return self._update_id

    def text_update(self, text: str, user_id: int = 111, chat_id: int = 111) -> dict:
        self._message_id += 1
        return {
            "update_id": self._next_update_id(),
            "message": {
                "message_id": self._message_id,
                "chat": {"id": chat_id, "type": "private"},
                "from": {"id": user_id, "first_name": "Tester"},
                "text": text,
            },
        }

    def callback_update(
        self,
        data: str,
        cb_id: str = "cb-1",
        user_id: int = 111,
        chat_id: int = 111,
    ) -> dict:
        self._message_id += 1
        return {
            "update_id": self._next_update_id(),
            "callback_query": {
                "id": cb_id,
                "from": {"id": user_id, "first_name": "Tester"},
                "message": {
                    "message_id": self._message_id,
                    "chat": {"id": chat_id, "type": "private"},
                },
                "data": data,
            },
        }

    def channel_post_update(self, text: str, chat_id: int = 500) -> dict:
        self._message_id += 1
        return {
            "update_id": self._next_update_id(),
            "channel_post": {
                "message_id": self._message_id,
                "chat": {"id": chat_id, "type": "channel"},
                "from": {"id": 777, "first_name": "Channel Admin"},
                "text": text,
            },
        }

    # -- HTTP handling -----------------------------------------------------
    def handler(self, request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        if method == "getUpdates":
            updates = self.updates
            self.updates = []
            return httpx.Response(200, json={"ok": True, "result": updates})
        if method == "answerCallbackQuery":
            if self.fail_answer:
                return httpx.Response(
                    400, json={"ok": False, "description": "unsupported by old client"}
                )
            body = json.loads(request.content)
            self.answered.append(body["callback_query_id"])
            return httpx.Response(200, json={"ok": True, "result": True})
        if method == "sendMessage":
            body = json.loads(request.content)
            self._message_id += 1
            self.sent.append(body)
            result = {"message_id": self._message_id}
            return httpx.Response(200, json={"ok": True, "result": result})
        return httpx.Response(404, json={"ok": False, "description": f"unknown method {method}"})

    # -- assertions helpers --------------------------------------------------
    def last_message(self) -> dict[str, Any]:
        assert self.sent, "no message was sent"
        return self.sent[-1]

    def keyboard_of(self, message: dict[str, Any]) -> list[list[dict[str, Any]]]:
        markup = message.get("reply_markup") or {}
        return markup.get("inline_keyboard", [])

    def callback_datas(self, message: dict[str, Any]) -> list[str]:
        rows = self.keyboard_of(message)
        return [btn.get("callback_data") or btn.get("url") for row in rows for btn in row]


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


# ----------------------------------------------------------------------
# Helper: drive one raw update through the handler
# ----------------------------------------------------------------------
async def drive(db_session, adapter, update: dict) -> None:
    await handlers.handle_update(db_session, adapter, "bale", update)


async def register_channel(db_session, fake_api, adapter, username: str) -> None:
    """Run the /addchannel → platform → id conversation for one channel."""
    await drive(db_session, adapter, fake_api.text_update("/addchannel"))
    await drive(db_session, adapter, fake_api.callback_update(kb.CMD_ADDCHANNEL))
    msg = fake_api.last_message()
    assert any(d == f"{kb.PLATFORM_PREFIX}bale" for d in fake_api.callback_datas(msg))
    await drive(db_session, adapter, fake_api.callback_update(f"{kb.PLATFORM_PREFIX}bale"))
    await drive(db_session, adapter, fake_api.text_update(username))


# ----------------------------------------------------------------------
# Button flows
# ----------------------------------------------------------------------
async def test_full_button_flow(db_session, fake_api, adapter, clean_states):
    """/RSAsecret → add channels → setsource → adddest → pause (all buttons)."""
    # --- /RSAsecret sends the manager welcome + main menu
    await drive(db_session, adapter, fake_api.text_update("/RSAsecret"))
    datas = fake_api.callback_datas(fake_api.last_message())
    assert kb.CMD_ADDCHANNEL in datas
    assert kb.CMD_MYCHANNELS in datas
    assert kb.CMD_SETSOURCE in datas
    assert kb.CMD_ADDDEST in datas
    assert kb.CMD_LINKS in datas
    assert kb.CMD_PAUSE in datas
    assert kb.CMD_STATUS in datas

    # --- button: ➕ افزودن کانال → platform picker → channel id
    await register_channel(db_session, fake_api, adapter, "@srcchan")
    await register_channel(db_session, fake_api, adapter, "@dstchan")

    channels = list((await db_session.execute(select(Channel))).scalars().all())
    assert {c.platform_channel_id for c in channels} == {"@srcchan", "@dstchan"}
    src = next(c for c in channels if c.platform_channel_id == "@srcchan")
    dst = next(c for c in channels if c.platform_channel_id == "@dstchan")

    # --- button: 🎯 تعیین مبدأ → channel button  (was broken: AttributeError)
    await drive(db_session, adapter, fake_api.text_update("/setsource"))
    datas = fake_api.callback_datas(fake_api.last_message())
    assert f"{kb.CHANNEL_PREFIX}{src.id}" in datas

    n_sent_before = len(fake_api.sent)
    await drive(db_session, adapter, fake_api.callback_update(f"{kb.CHANNEL_PREFIX}{src.id}"))
    assert len(fake_api.sent) > n_sent_before, "channel button produced no reply"
    assert "✅" in fake_api.last_message()["text"]

    await db_session.refresh(src)
    assert src.role == ChannelRole.SOURCE
    assert state_machine.get("bale", "111").state == States.IDLE  # state reset

    # --- button: 🔗 افزودن مقصد → source button → destination button
    await drive(db_session, adapter, fake_api.text_update("/adddest"))
    datas = fake_api.callback_datas(fake_api.last_message())
    assert f"{kb.CHANNEL_PREFIX}{src.id}" in datas

    await drive(db_session, adapter, fake_api.callback_update(f"{kb.CHANNEL_PREFIX}{src.id}"))
    datas = fake_api.callback_datas(fake_api.last_message())
    assert f"{kb.CHANNEL_PREFIX}{dst.id}" in datas

    n_sent_before = len(fake_api.sent)
    await drive(db_session, adapter, fake_api.callback_update(f"{kb.CHANNEL_PREFIX}{dst.id}"))
    assert len(fake_api.sent) > n_sent_before, "destination button produced no reply"
    assert "🎉" in fake_api.last_message()["text"]

    links = list((await db_session.execute(select(SyncLink))).scalars().all())
    assert len(links) == 1
    assert links[0].source_channel_id == src.id
    assert links[0].destination_channel_id == dst.id

    # --- button: ⏸ توقف/ادامه → link toggle button  (was broken)
    await drive(db_session, adapter, fake_api.text_update("/pause"))
    datas = fake_api.callback_datas(fake_api.last_message())
    assert f"{kb.LINK_PREFIX}{links[0].id}" in datas

    n_sent_before = len(fake_api.sent)
    await drive(db_session, adapter, fake_api.callback_update(f"{kb.LINK_PREFIX}{links[0].id}"))
    assert len(fake_api.sent) > n_sent_before, "link toggle button produced no reply"

    await db_session.refresh(links[0])
    assert links[0].is_active is False

    # toggle back on
    await drive(db_session, adapter, fake_api.text_update("/pause"))
    await drive(db_session, adapter, fake_api.callback_update(f"{kb.LINK_PREFIX}{links[0].id}"))
    await db_session.refresh(links[0])
    assert links[0].is_active is True


async def test_cancel_button_resets_state(db_session, fake_api, adapter, clean_states):
    await drive(db_session, adapter, fake_api.text_update("/addchannel"))
    assert state_machine.get("bale", "111").state == States.AWAIT_CHANNEL_PLATFORM
    await drive(db_session, adapter, fake_api.callback_update(kb.CANCEL))
    assert state_machine.get("bale", "111").state == States.IDLE
    assert "لغو" in fake_api.last_message()["text"]


async def test_duplicate_channel_not_created_twice(db_session, fake_api, adapter, clean_states):
    await register_channel(db_session, fake_api, adapter, "@same")
    await register_channel(db_session, fake_api, adapter, "@same")

    channels = list((await db_session.execute(select(Channel))).scalars().all())
    assert len(channels) == 1


# ----------------------------------------------------------------------
# answerCallbackQuery must never break button handling (Bale docs)
# ----------------------------------------------------------------------
async def test_old_client_callback_still_works(db_session, fake_api, adapter, clean_states):
    """callback_query_id starting with '1' → old client, feature unsupported.

    The handler must still run; answerCallbackQuery must NOT be called.
    """
    await register_channel(db_session, fake_api, adapter, "@srcchan")
    src = (await db_session.execute(select(Channel))).scalars().first()

    await drive(db_session, adapter, fake_api.text_update("/setsource"))
    # Old-client ids start with "1"
    await drive(
        db_session,
        adapter,
        fake_api.callback_update(f"{kb.CHANNEL_PREFIX}{src.id}", cb_id="1000000001"),
    )
    # Old-client id: answerCallbackQuery must NOT have been attempted.
    assert "1000000001" not in fake_api.answered
    # But the button handler itself must still have completed.
    assert "✅" in fake_api.last_message()["text"]


async def test_answer_failure_does_not_kill_button(db_session, fake_api, adapter, clean_states):
    """Even if answerCallbackQuery errors, the button handler must complete."""
    fake_api.fail_answer = True
    await drive(db_session, adapter, fake_api.text_update("/start"))
    n = len(fake_api.sent)
    await drive(db_session, adapter, fake_api.callback_update(kb.CMD_MYCHANNELS))
    # /mychannels with no channels replies with a hint message
    assert len(fake_api.sent) == n + 1
    assert "هنوز کانالی" in fake_api.last_message()["text"]


# ----------------------------------------------------------------------
# Manager UI must not talk in channels/groups (single-bot deployments)
# ----------------------------------------------------------------------
async def test_channel_posts_ignored_by_manager_ui(
    db_session, fake_api, adapter, clean_states
):
    n = len(fake_api.sent)
    await drive(db_session, adapter, fake_api.channel_post_update("hello from channel"))
    assert len(fake_api.sent) == n, "manager replied inside the channel"


async def test_channel_posts_still_reach_sync_pipeline(
    db_session, fake_api, adapter, clean_states, monkeypatch
):
    """dispatch_sync_update (used by the manager loop) feeds channel posts."""
    from app.pollers.base import dispatch_sync_update
    from app.services import sync_service

    user_id = 42
    await channel_service.add_channel(
        db_session, user_id,
        ChannelCreate(platform="bale", platform_channel_id="500", title="Src", role="source"),
    )
    await channel_service.add_channel(
        db_session, user_id,
        ChannelCreate(platform="bale", platform_channel_id="600", title="Dst", role="destination"),
    )
    from app.models import SyncLink as SL

    src = (await db_session.execute(
        select(Channel).where(Channel.platform_channel_id == "500")
    )).scalars().first()
    link = SL(user_id=user_id, source_channel_id=src.id, destination_channel_id=src.id + 1)
    db_session.add(link)
    await db_session.commit()

    enqueued: list[dict] = []

    class _Q:
        async def enqueue(self, item):
            enqueued.append(item)

        async def dequeue(self, timeout=1.0):
            return None

    monkeypatch.setattr(sync_service, "get_queue", lambda: _Q())

    update = fake_api.channel_post_update("sync me", chat_id=500)
    await dispatch_sync_update(adapter, lambda: nullcontext(db_session), update)

    assert len(enqueued) == 1
    assert enqueued[0]["message"]["text"] == "sync me"


# ----------------------------------------------------------------------
# build_polling_adapters must not double-consume the manager bot's updates
# ----------------------------------------------------------------------
def test_poller_skipped_when_token_equals_manager_token(monkeypatch):
    from app.adapters import Platform
    from app.config import get_settings
    from app.pollers import build_polling_adapters

    settings = get_settings()
    monkeypatch.setattr(settings, "bale_bot_token", "SHARED")
    monkeypatch.setattr(settings, "manager_bot_token", "SHARED")
    adapters = build_polling_adapters()
    assert Platform.BALE not in adapters

    monkeypatch.setattr(settings, "bale_bot_token", "OTHER")
    adapters = build_polling_adapters()
    assert Platform.BALE in adapters


# ----------------------------------------------------------------------
# Guards added in the post-audit hardening pass
# ----------------------------------------------------------------------
async def register_channel_on_platform(
    db_session, fake_api, adapter, platform: str, username: str
) -> None:
    """/addchannel → <platform> picker → channel id."""
    await drive(db_session, adapter, fake_api.text_update("/addchannel"))
    await drive(db_session, adapter, fake_api.callback_update(kb.CMD_ADDCHANNEL))
    msg = fake_api.last_message()
    assert any(d == f"{kb.PLATFORM_PREFIX}{platform}" for d in fake_api.callback_datas(msg))
    await drive(db_session, adapter, fake_api.callback_update(f"{kb.PLATFORM_PREFIX}{platform}"))
    await drive(db_session, adapter, fake_api.text_update(username))


async def test_setsource_rejects_destination_only_platform(
    db_session, fake_api, adapter, clean_states
):
    """An Eitaa channel (supports_source=False) must not be set as source."""
    await register_channel_on_platform(db_session, fake_api, adapter, "eitaa", "12345")
    channels = list((await db_session.execute(select(Channel))).scalars().all())
    assert len(channels) == 1
    eitaa_channel = channels[0]
    assert eitaa_channel.role == ChannelRole.DESTINATION

    await drive(db_session, adapter, fake_api.text_update("/setsource"))
    await drive(
        db_session, adapter, fake_api.callback_update(f"{kb.CHANNEL_PREFIX}{eitaa_channel.id}")
    )

    text = fake_api.last_message()["text"]
    assert "مبدأ" in text or "⚠️" in text
    await db_session.refresh(eitaa_channel)
    msg = "role must not change for a rejected source"
    assert eitaa_channel.role == ChannelRole.DESTINATION, msg
    assert state_machine.get("bale", "111").state == States.AWAIT_SOURCE_SELECT


async def test_duplicate_link_rejected(db_session, fake_api, adapter, clean_states):
    """Creating the same (source, destination) link twice must not duplicate it."""
    await register_channel(db_session, fake_api, adapter, "@src2")
    await register_channel(db_session, fake_api, adapter, "@dst2")
    channels = list((await db_session.execute(select(Channel))).scalars().all())
    src = next(c for c in channels if c.platform_channel_id == "@src2")
    dst = next(c for c in channels if c.platform_channel_id == "@dst2")

    # First link: /setsource → /adddest → src → dst
    await drive(db_session, adapter, fake_api.text_update("/setsource"))
    await drive(db_session, adapter, fake_api.callback_update(f"{kb.CHANNEL_PREFIX}{src.id}"))
    await drive(db_session, adapter, fake_api.text_update("/adddest"))
    await drive(db_session, adapter, fake_api.callback_update(f"{kb.CHANNEL_PREFIX}{src.id}"))
    await drive(db_session, adapter, fake_api.callback_update(f"{kb.CHANNEL_PREFIX}{dst.id}"))
    links = list((await db_session.execute(select(SyncLink))).scalars().all())
    assert len(links) == 1

    # Second attempt with the same pair: must be rejected, no new row
    await drive(db_session, adapter, fake_api.text_update("/adddest"))
    await drive(db_session, adapter, fake_api.callback_update(f"{kb.CHANNEL_PREFIX}{src.id}"))
    await drive(db_session, adapter, fake_api.callback_update(f"{kb.CHANNEL_PREFIX}{dst.id}"))
    assert "قبلاً" in fake_api.last_message()["text"]
    links = list((await db_session.execute(select(SyncLink))).scalars().all())
    assert len(links) == 1, "duplicate link must not be created"


async def test_corrupt_callback_data_does_not_crash(db_session, fake_api, adapter, clean_states):
    """A non-numeric channel:/link: payload must not kill the handler."""
    await drive(db_session, adapter, fake_api.text_update("/start"))
    before = len(fake_api.sent)
    await drive(db_session, adapter, fake_api.callback_update(f"{kb.CHANNEL_PREFIX}not-a-number"))
    assert len(fake_api.sent) > before
    assert "نامعتبر" in fake_api.last_message()["text"]
    await drive(db_session, adapter, fake_api.callback_update(f"{kb.LINK_PREFIX}xyz"))
    assert "نامعتبر" in fake_api.last_message()["text"]


async def test_empty_destination_picker_gives_hint(db_session, fake_api, adapter, clean_states):
    """/adddest with a source but no destination channels registered must explain."""
    await register_channel(db_session, fake_api, adapter, "@onlysrc")
    channels = list((await db_session.execute(select(Channel))).scalars().all())
    src = channels[0]
    await drive(db_session, adapter, fake_api.text_update("/setsource"))
    await drive(db_session, adapter, fake_api.callback_update(f"{kb.CHANNEL_PREFIX}{src.id}"))

    await drive(db_session, adapter, fake_api.text_update("/adddest"))
    await drive(db_session, adapter, fake_api.callback_update(f"{kb.CHANNEL_PREFIX}{src.id}"))
    assert "مقصد" in fake_api.last_message()["text"]
    assert "/addchannel" in fake_api.last_message()["text"]
    assert state_machine.get("bale", "111").state == States.IDLE


# ----------------------------------------------------------------------
# run_manager loop: single-bot mode (manager token == source listener)
# ----------------------------------------------------------------------
async def test_run_manager_single_bot_mode(db_session, fake_api, clean_states, monkeypatch):
    """The manager loop must sync channel posts AND answer private commands.

    In single-bot mode the manager loop is the only ``getUpdates`` consumer:
    channel posts go to the sync pipeline, private messages to the manager UI.
    """
    import asyncio

    from app.bot_manager import manager as mgr
    from app.config import get_settings
    from app.services import sync_service, user_service
    from app.services.cache_service import cache_service

    user = await user_service.get_or_create_user(db_session, "bale", "111")
    src = await channel_service.add_channel(
        db_session,
        user.id,
        ChannelCreate(
            platform="bale", platform_channel_id="500", title="Src",
            role=ChannelRole.SOURCE,
        ),
    )
    dst = await channel_service.add_channel(
        db_session,
        user.id,
        ChannelCreate(
            platform="bale", platform_channel_id="600", title="Dst",
            role=ChannelRole.DESTINATION,
        ),
    )
    db_session.add(
        SyncLink(user_id=user.id, source_channel_id=src.id, destination_channel_id=dst.id)
    )
    await db_session.commit()

    enqueued: list[dict] = []

    class _Q:
        async def enqueue(self, item):
            enqueued.append(item)

        async def dequeue(self, timeout=1.0):
            return None

        async def close(self):
            pass

    monkeypatch.setattr(sync_service, "get_queue", lambda: _Q())

    # One source-channel post + one private /RSAsecret, then idle.
    fake_api.updates = [
        fake_api.channel_post_update("hello from source", chat_id=500),
        fake_api.text_update("/RSAsecret"),
    ]

    settings = get_settings()
    monkeypatch.setattr(settings, "manager_bot_token", "TOKEN")
    monkeypatch.setattr(settings, "manager_bot_platform", "bale")

    client = httpx.AsyncClient(transport=httpx.MockTransport(fake_api.handler))
    adapter = BaleAdapter("TOKEN", client=client)
    monkeypatch.setattr(mgr, "build_adapter", lambda platform, token: adapter)

    task = asyncio.create_task(mgr.run_manager())
    deadline = asyncio.get_running_loop().time() + 10
    while len(enqueued) < 1 or not fake_api.sent:
        if asyncio.get_running_loop().time() > deadline:
            break
        await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # The channel post was routed to the sync pipeline (single-bot mode).
    assert len(enqueued) == 1
    assert enqueued[0]["message"]["text"] == "hello from source"
    assert enqueued[0]["message"]["chat_id"] == "500"
    assert enqueued[0]["source_channel_id"] == src.id
    assert enqueued[0]["sync_link_ids"], "job must carry the matching link ids"

    # The private /RSAsecret was answered by the manager UI (with a menu).
    assert fake_api.sent, "manager should have answered /RSAsecret"
    menu = fake_api.last_message()
    assert kb.CMD_ADDCHANNEL in fake_api.callback_datas(menu)

    await adapter.close()
    await client.aclose()
    cache_service.clear()
