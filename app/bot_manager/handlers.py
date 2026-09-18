"""Manager bot command and callback handlers.

These handlers are deliberately framework-agnostic: they receive a raw
``update`` dict plus an adapter and a database session, and are driven by the
polling loop in :mod:`app.bot_manager.manager`. Every user action is logged to
the terminal via :func:`app.utils.logger.log_user_event`.
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters import AbstractAdapter, AdapterError, InlineKeyboardMarkup
from app.bot_manager import keyboards as kb
from app.bot_manager.states import States, state_machine
from app.models import Channel, SyncLink, User
from app.models.channel import ChannelRole
from app.schemas.channel import ChannelCreate
from app.services import cache_service, channel_service, user_service
from app.utils.logger import log_user_event

HELP_TEXT = """\
دستورات ربات:
/start — منوی اصلی
/addchannel — افزودن کانال
/mychannels — لیست کانال‌ها
/setsource — تعیین کانال مبدأ
/adddest — افزودن کانال مقصد و ساخت لینک
/links — مشاهده لینک‌های همگام‌سازی
/pause — غیرفعال‌کردن یک لینک
/resume — فعال‌کردن یک لینک
/status — وضعیت سیستم
/help — راهنما
"""

# Maps main-menu button callbacks to their equivalent text command.
_CMD_ROUTES = {
    kb.CMD_ADDCHANNEL: "/addchannel",
    kb.CMD_MYCHANNELS: "/mychannels",
    kb.CMD_SETSOURCE: "/setsource",
    kb.CMD_ADDDEST: "/adddest",
    kb.CMD_LINKS: "/links",
    kb.CMD_PAUSE: "/pause",
    kb.CMD_STATUS: "/status",
}


async def handle_update(
    session: AsyncSession,
    adapter: AbstractAdapter,
    platform: str,
    update: dict[str, Any],
) -> None:
    """Route a single raw update to the correct handler."""
    if "callback_query" in update:
        await _handle_callback(session, adapter, platform, update["callback_query"])
        return

    msg = update.get("message") or update.get("channel_post")
    if not isinstance(msg, dict):
        return

    chat = msg.get("chat") or {}
    sender = msg.get("from") or {}
    chat_id = str(chat.get("id", ""))
    user_id = str(sender.get("id", ""))
    text = (msg.get("text") or "").strip()

    if not chat_id or not user_id:
        return

    user = await user_service.get_or_create_user(
        session, platform, user_id, sender.get("username")
    )
    ctx = state_machine.get(platform, user_id)

    if text.startswith("/"):
        await _handle_command(session, adapter, platform, user, chat_id, text)
        return

    await _handle_text(session, adapter, platform, user, chat_id, text, ctx)


# ----------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------
async def _handle_command(
    session: AsyncSession,
    adapter: AbstractAdapter,
    platform: str,
    user: User,
    chat_id: str,
    text: str,
) -> None:
    command = text.split()[0].lower().split("@")[0]
    user_id = user.platform_user_id
    ctx = state_machine.get(platform, user_id)
    log_user_event(platform, user_id, "command", command=command)

    if command == "/start":
        state_machine.reset(platform, user_id)
        await _send(
            adapter,
            chat_id,
            "سلام! 👋\nبا این ربات می‌توانید کانال‌های خود را در بله، ایتا و روبیکا همگام کنید.",
            kb.main_menu(),
        )
    elif command == "/help":
        await _send(adapter, chat_id, HELP_TEXT)
    elif command == "/addchannel":
        state_machine.set_state(platform, user_id, States.AWAIT_CHANNEL_PLATFORM)
        await _send(adapter, chat_id, "پلتفرم کانال را انتخاب کنید:", kb.platform_picker())
    elif command == "/mychannels":
        await _cmd_mychannels(session, adapter, platform, user, chat_id)
    elif command == "/setsource":
        channels = await channel_service.list_channels(session, user.id)
        if not channels:
            await _send(adapter, chat_id, "هنوز کانالی ثبت نکرده‌اید. /addchannel")
            return
        state_machine.set_state(platform, user_id, States.AWAIT_SOURCE_SELECT)
        await _send(adapter, chat_id, "کانال مبدأ را انتخاب کنید:", kb.channel_picker(channels, kb.CHANNEL_PREFIX))
    elif command == "/adddest":
        sources = await _channels_with_role(session, user.id, ChannelRole.SOURCE)
        if not sources:
            await _send(adapter, chat_id, "اول یک کانال مبدأ تعیین کنید. /setsource")
            return
        state_machine.set_state(platform, user_id, States.AWAIT_DEST_SELECT, source_id=None)
        await _send(adapter, chat_id, "کانال مبدأ را انتخاب کنید:", kb.channel_picker(sources, kb.CHANNEL_PREFIX))
    elif command == "/links":
        await _cmd_links(session, adapter, platform, user, chat_id)
    elif command in ("/pause", "/resume"):
        links = await _list_links(session, user.id)
        if not links:
            await _send(adapter, chat_id, "هنوز لینکی نساخته‌اید. /adddest")
            return
        state_machine.set_state(platform, user_id, States.AWAIT_LINK_TOGGLE)
        await _send(adapter, chat_id, "لینک موردنظر را انتخاب کنید:", kb.link_picker(links))
    elif command == "/status":
        await _cmd_status(session, adapter, platform, user, chat_id)
    else:
        await _send(adapter, chat_id, "دستور ناشناخته. /help")


async def _cmd_mychannels(session, adapter, platform, user, chat_id) -> None:
    channels = await channel_service.list_channels(session, user.id)
    if not channels:
        await _send(adapter, chat_id, "هنوز کانالی ثبت نکرده‌اید. /addchannel")
        return
    lines = ["کانال‌های شما:"]
    for c in channels:
        role = "مبدأ" if c.role == ChannelRole.SOURCE else "مقصد"
        active = "فعال" if c.is_active else "غیرفعال"
        lines.append(f"• {c.title or c.platform_channel_id} [{c.platform}] — {role} — {active}")
    await _send(adapter, chat_id, "\n".join(lines))
    log_user_event(platform, user.platform_user_id, "mychannels", count=len(channels))


async def _cmd_links(session, adapter, platform, user, chat_id) -> None:
    links = await _list_links(session, user.id)
    if not links:
        await _send(adapter, chat_id, "هنوز لینکی نساخته‌اید. /adddest")
        return
    lines = ["لینک‌های همگام‌سازی:"]
    for l in links:
        state = "فعال" if l.is_active else "غیرفعال"
        src = l.source_channel.title or l.source_channel.platform_channel_id
        dst = l.destination_channel.title or l.destination_channel.platform_channel_id
        lines.append(f"• #{l.id}: {src} → {dst} — {state}")
    await _send(adapter, chat_id, "\n".join(lines))


async def _cmd_status(session, adapter, platform, user, chat_id) -> None:
    n_channels = await _count(session, Channel, Channel.user_id == user.id)
    n_links = await _count(session, SyncLink, SyncLink.user_id == user.id)
    await _send(
        adapter,
        chat_id,
        f"📊 وضعیت سیستم:\nکانال‌ها: {n_channels}\nلینک‌ها: {n_links}",
    )
    log_user_event(platform, user.platform_user_id, "status", channels=n_channels, links=n_links)


# ----------------------------------------------------------------------
# Callbacks
# ----------------------------------------------------------------------
async def _handle_callback(
    session: AsyncSession,
    adapter: AbstractAdapter,
    platform: str,
    cb: dict[str, Any],
) -> None:
    data = cb.get("data") or ""
    cb_id = cb.get("id", "")
    sender = cb.get("from") or {}
    msg = cb.get("message") or {}
    user_id = str(sender.get("id", ""))
    chat_id = str(msg.get("chat", {}).get("id", "") or sender.get("id", ""))

    await adapter.answer_callback_query(cb_id)

    user = await user_service.get_or_create_user(session, platform, user_id, sender.get("username"))
    ctx = state_machine.get(platform, user_id)
    log_user_event(platform, user_id, "button", data=data)

    if data == kb.CANCEL:
        state_machine.reset(platform, user_id)
        await _send(adapter, chat_id, "عملیات لغو شد.", kb.main_menu())
        return

    # Route main-menu buttons to their equivalent command handlers.
    if data in _CMD_ROUTES:
        await _handle_command(session, adapter, platform, user, chat_id, _CMD_ROUTES[data])
        return

    if data.startswith(kb.PLATFORM_PREFIX):
        chosen = data[len(kb.PLATFORM_PREFIX):]
        state_machine.set_state(platform, user_id, States.AWAIT_CHANNEL_ID, platform=chosen)
        await _send(adapter, chat_id, f"آیدی کانال {chosen} را ارسال کنید (عددی یا @username):")
        return

    if data.startswith(kb.CHANNEL_PREFIX):
        channel_id = int(data[len(kb.CHANNEL_PREFIX):])
        await _on_channel_selected(session, adapter, platform, user, chat_id, channel_id, ctx)
        return

    if data.startswith(kb.LINK_PREFIX):
        link_id = int(data[len(kb.LINK_PREFIX):])
        await _toggle_link(session, adapter, platform, user, chat_id, link_id)
        return


async def _on_channel_selected(
    session, adapter, platform, user, chat_id, channel_id, ctx
) -> None:
    if ctx.state == States.AWAIT_SOURCE_SELECT:
        channel = await channel_service.get_channel(session, channel_id, user.id)
        if channel is None:
            await _send(adapter, chat_id, "کانال یافت نشد.")
            return
        channel.role = ChannelRole.SOURCE
        await session.commit()
        cache_service.invalidate_channel(channel.platform)
        cache_service.invalidate_links()
        state_machine.reset(platform, user.platform_user_id)
        log_user_event(
            platform, user.platform_user_id, "setsource", channel_id=channel.platform_channel_id
        )
        await _send(adapter, chat_id, "✅ کانال مبدأ تنظیم شد.", kb.main_menu())
    elif ctx.state == States.AWAIT_DEST_SELECT:
        if ctx.data.get("source_id") is None:
            source = await channel_service.get_channel(session, channel_id, user.id)
            if source is None:
                await _send(adapter, chat_id, "کانال یافت نشد.")
                return
            ctx.data["source_id"] = channel_id
            dests = await _channels_with_role(session, user.id, ChannelRole.DESTINATION)
            await _send(adapter, chat_id, "کانال مقصد را انتخاب کنید:", kb.channel_picker(dests, kb.CHANNEL_PREFIX))
        else:
            source_id = int(ctx.data["source_id"])
            if source_id == channel_id:
                await _send(adapter, chat_id, "مبدأ و مقصد نمی‌توانند یکسان باشند.")
                return
            link = SyncLink(user_id=user.id, source_channel_id=source_id, destination_channel_id=channel_id)
            session.add(link)
            await session.commit()
            cache_service.invalidate_links(source_id)
            state_machine.reset(platform, user.platform_user_id)
            log_user_event(
                platform, user.platform_user_id, "create_link", source_id=source_id, dest_id=channel_id
            )
            await _send(adapter, chat_id, "✅ لینک همگام‌سازی ساخته شد.", kb.main_menu())


async def _toggle_link(session, adapter, platform, user, chat_id, link_id) -> None:
    link = await session.get(SyncLink, link_id)
    if link is None or link.user_id != user.id:
        await _send(adapter, chat_id, "لینک یافت نشد.")
        return
    link.is_active = not link.is_active
    await session.commit()
    cache_service.invalidate_links()
    state = "فعال" if link.is_active else "غیرفعال"
    log_user_event(platform, user.platform_user_id, "toggle_link", link_id=link.id, active=link.is_active)
    await _send(adapter, chat_id, f"لینک #{link.id} {state} شد.")


# ----------------------------------------------------------------------
# Text input (state-driven)
# ----------------------------------------------------------------------
async def _handle_text(
    session, adapter, platform, user, chat_id, text, ctx
) -> None:
    if ctx.state == States.AWAIT_CHANNEL_ID:
        chosen = ctx.data.get("platform", platform)
        title = text.lstrip("@")
        try:
            await channel_service.add_channel(
                session,
                user.id,
                ChannelCreate(
                    platform=chosen,
                    platform_channel_id=text.strip(),
                    title=title,
                    role=ChannelRole.DESTINATION,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to add channel: {}", exc)
            await _send(adapter, chat_id, "ثبت کانال ناموفق بود. دوباره تلاش کنید.")
            return
        cache_service.invalidate_channel(chosen)
        state_machine.reset(platform, user.platform_user_id)
        log_user_event(
            platform, user.platform_user_id, "addchannel", platform=chosen, id=text.strip()
        )
        await _send(
            adapter,
            chat_id,
            "✅ کانال ثبت شد.\n⚠️ فراموش نکنید ربات را در کانال ادمین کنید.",
            kb.main_menu(),
        )
    else:
        await _send(adapter, chat_id, "از منوی اصلی استفاده کنید. /start")


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
async def _send(
    adapter: AbstractAdapter,
    chat_id: str,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
) -> None:
    try:
        await adapter.send_message(chat_id, text, reply_markup=keyboard)
    except AdapterError as exc:
        logger.error("Manager failed to send message: {}", exc)


async def _channels_with_role(session, user_id, role) -> list[Channel]:
    stmt = select(Channel).where(Channel.user_id == user_id, Channel.role == role)
    return list((await session.execute(stmt)).scalars().all())


async def _list_links(session, user_id) -> list[SyncLink]:
    stmt = (
        select(SyncLink)
        .where(SyncLink.user_id == user_id)
        .options(
            selectinload(SyncLink.source_channel),
            selectinload(SyncLink.destination_channel),
        )
    )
    return list((await session.execute(stmt)).scalars().all())


async def _count(session, model, condition) -> int:
    stmt = select(func.count()).select_from(model).where(condition)
    return int((await session.execute(stmt)).scalar_one())
