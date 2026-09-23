"""In-process bridge to the anonymous-message ("درگوشی") bot flows.

The anonymous-link feature is a self-contained, synchronous codebase copied
verbatim into ``anon_bot/``.  This bridge loads it with the sync bot's own
Bale token and exposes async entry points that execute its handlers in a
single worker thread — so the shared ``sqlite3`` connection stays consistent
and the async event loop is never blocked by the synchronous ``requests``
calls the anonymous flows make.
"""

from __future__ import annotations

import asyncio
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from loguru import logger

from app.config import get_settings

# Callback that opens the anonymous-link panel (used by the inline button we
# attach to the public ``/start`` message).
ANON_PANEL = "anon_panel"

_ANON_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "anon_bot"
)

_lock = threading.Lock()
_executor: ThreadPoolExecutor | None = None
_handlers: dict[str, Any] = {}
_loaded = False

# Callback families handled by the anonymous bot (see anon_bot/main.py).
_INLINE_PREFIXES = (
    "alink_edit_",
    "alink_seen_",
    "alink_reply_",
    "alink_react_",
    "alink_remoji_",
    "alink_rback_",
    "alink_tochannel_",
)
_PANEL_PREFIXES = ("anol_", "anon_", "m_", "blk_", "unblock_")
_PANEL_EXACT = {"nav_back", "cancel_waiting", "m_main", "no_action"}


def _load() -> None:
    """Import the anonymous bot once, with the sync bot's token injected."""
    global _executor, _loaded
    if _loaded:
        return

    settings = get_settings()
    token = settings.manager_bot_token or settings.bale_bot_token
    if token:
        # anon_bot/config.py reads this before building its BASE_URL.
        os.environ["ANON_BOT_TOKEN"] = token

    if _ANON_DIR not in sys.path:
        sys.path.insert(0, _ANON_DIR)

    from database import add_user
    from handlers.anonymous_link import (
        handle_anonymous_delete,
        handle_anonymous_inline_callback,
        show_anonymous_panel,
    )
    from handlers.group import handle_group
    from handlers.private import handle_private
    from handlers.private_callbacks import handle_private_callback

    _handlers.update(
        add_user=add_user,
        handle_group=handle_group,
        handle_private=handle_private,
        handle_private_callback=handle_private_callback,
        handle_anonymous_delete=handle_anonymous_delete,
        handle_anonymous_inline_callback=handle_anonymous_inline_callback,
        show_anonymous_panel=show_anonymous_panel,
    )
    _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="anon-bot")
    _loaded = True
    logger.info("Anonymous-message flows loaded from {}", _ANON_DIR)


async def _call(name: str, *args: Any) -> None:
    """Run an anonymous handler in the dedicated worker thread."""
    _load()
    fn = _handlers[name]
    loop = asyncio.get_running_loop()

    def run() -> None:
        with _lock:
            try:
                fn(*args)
            except Exception:  # noqa: BLE001 - never break the manager loop
                logger.exception("Anonymous flow {!r} failed", name)

    assert _executor is not None
    await loop.run_in_executor(_executor, run)


def is_anon_callback(data: str) -> bool:
    """Whether ``data`` belongs to the anonymous bot (vs the sync manager)."""
    if data == ANON_PANEL:
        return True
    return (
        data.startswith("anon_delete_")
        or data.startswith(_INLINE_PREFIXES)
        or data.startswith(_PANEL_PREFIXES)
        or data in _PANEL_EXACT
    )


async def open_panel(chat_id: str, user_id: str) -> None:
    """Open the anonymous-links panel for ``user_id``."""
    await _call("add_user", user_id)
    await _call("show_anonymous_panel", chat_id, user_id)


async def handle_callback(
    data: str,
    callback_id: str,
    user_id: str,
    message_id: str | None,
    chat_id: str,
) -> None:
    """Dispatch an anonymous-bot callback query."""
    if data == ANON_PANEL:
        await open_panel(chat_id, user_id)
    elif data.startswith("anon_delete_"):
        await _call(
            "handle_anonymous_delete", data, callback_id, user_id, message_id, chat_id
        )
    elif data.startswith(_INLINE_PREFIXES):
        await _call(
            "handle_anonymous_inline_callback",
            data,
            callback_id,
            user_id,
            message_id,
            chat_id,
        )
    else:
        await _call(
            "handle_private_callback",
            data,
            callback_id,
            user_id,
            message_id,
            chat_id,
        )


async def handle_message(
    chat_id: str,
    user_id: str,
    text: str,
    msg: dict[str, Any] | None,
) -> None:
    """Dispatch a private message to the anonymous-bot text handler."""
    await _call("handle_private", chat_id, user_id, text, msg)


async def handle_group_message(
    chat_id: str,
    user_id: str,
    text: str,
    message_id: str | None,
    msg: dict[str, Any] | None,
) -> None:
    """Dispatch a group message to the anonymous-bot group handler."""
    await _call("handle_group", chat_id, user_id, text, message_id, msg)
