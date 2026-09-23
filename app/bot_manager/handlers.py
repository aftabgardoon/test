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

from app import anon_bridge
from app.adapters import (
    AbstractAdapter,
    AdapterError,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    platform_supports_source,
)
from app.bot_manager import keyboards as kb
from app.bot_manager.states import States, state_machine
from app.config import get_settings
from app.models import Channel, SyncLink, User
from app.models.channel import ChannelRole
from app.schemas.channel import ChannelCreate
from app.services import access_service, channel_service, user_service
from app.services.cache_service import cache_service
from app.utils.logger import log_user_event

WELCOME_TEXT = """\
👋 سلام! به **بات همگام‌سازی چندکاناله** خوش آمدی.

🎯 **این بات چیه؟**
این بات به تو کمک می‌کنه پیام‌هایی که توی یک کانال می‌ذاری، به صورت خودکار
و با همون ظاهر (متن، عکس، ویدیو، ویس، فایل، استیکر و...) توی کانال‌های
دیگه‌ات (توی بله، ایتا و روبیکا) هم منتشر بشن.

💡 **چرا به دردت می‌خوره؟**
اگه چند تا کانال داری و نمی‌خوای هر پیام رو دستی توی همه‌شون بذاری،
این بات کارت رو راحت می‌کنه. یه بار پیام می‌ذاری، خودش همه‌جا پخش می‌شه.

📋 **برای شروع، این مراحل رو دنبال کن:**

**مرحله ۱ — ثبت توکن ربات:**
   توکن ربات‌های بله/ایتا/روبیکا رو با دستور /settoken ثبت کن.

**مرحله ۲ — افزودن کانال:**
   با دستور /addchannel کانال مبدأ و مقصد رو ثبت کن.
   ⚠️ یادت باشه ربات رو توی کانال **ادمین** کنی.

**مرحله ۳ — تعیین مبدأ:**
   با دستور /setsource مشخص کن کدوم کانال پیام‌ها رو می‌فرسته.

**مرحله ۴ — افزودن مقصد:**
   با دستور /adddest کانال‌های مقصد رو وصل کن.

**مرحله ۵ — تمام!** 🎉
   از این به بعد هر پیامی توی کانال مبدأ بذاری، خودش توی مقصدها منتشر می‌شه.

❓ **اگه گیج شدی یا سوالی داشتی، دستور /help رو بزن.**
"""

HELP_TEXT = """\
📖 **راهنمای کامل بات**

🔧 **دستورات موجود:**

• /start — شروع و توضیحات اولیه
• /settoken — ثبت توکن ربات‌های بله، ایتا، روبیکا
• /addchannel — افزودن کانال جدید
• /mychannels — مشاهده و حذف کانال‌های من
• /setsource — تعیین کانال مبدأ (فرستنده)
• /adddest — افزودن کانال مقصد (گیرنده)
• /links — مشاهده لینک‌های همگام‌سازی
• /pause — توقف موقت یک لینک
• /resume — فعال‌سازی مجدد یک لینک
• /status — وضعیت کلی سیستم
• /help — همین راهنما

💡 **نکات مهم:**

۱. ربات باید توی هر کانال (مبدأ و مقصد) **ادمین** باشه.
۲. برای بله و روبیکا، ربات هم می‌تونه مبدأ باشه هم مقصد.
۳. **ایتا فقط مقصد می‌تونه باشه** (به دلیل محدودیت API).
۴. برای حذف کانال، از /mychannels استفاده کن.

🆘 **اگه مشکلی داشتی:**
- چک کن ربات توی کانال ادمین باشه.
- چک کن توکن‌ها درست ثبت شده باشن.
- از /status برای دیدن وضعیت استفاده کن.
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

# Secret command that unlocks the manager UI (compared case-insensitively).
# Users send "/RSAsecret" (or "/RSAsecret <value>" when a custom
# ``MANAGER_ACCESS_SECRET`` is configured).
SECRET_COMMAND = "/rsasecret"

# Sync-manager text commands (gated behind /RSAsecret).  Anything else in a
# private chat is handled by the public anonymous-message flows.
_SYNC_COMMANDS = {
    "/help",
    "/addchannel",
    "/mychannels",
    "/setsource",
    "/adddest",
    "/links",
    "/pause",
    "/resume",
    "/status",
    "/settoken",
}

# Public landing shown to everyone who sends /start.  This is the intro of the
# anonymous-message ("درگوشی") bot; the button under it opens the anonymous
# panel inside *this* bot (no redirect).
PUBLIC_START_TEXT = """\
👻 *ربات لینک ناشناس*

با این ربات میتونی لینک ناشناس بسازی و از دوستات نظر و پیام ناشناس بگیری.

🔗 *لینک ناشناس:* یه لینک بساز، بفرست برای دوستات تا ناشناس بهت پیام بدن.

📌 برای شروع، روی دکمه «🔗 لینک ناشناس» بزن."""


async def _handle_public_start(
    adapter: AbstractAdapter,
    chat_id: str,
) -> None:
    """Send the anonymous-bot intro for the public ``/start`` command."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 لینک ناشناس", callback_data=anon_bridge.ANON_PANEL
                )
            ]
        ]
    )
    await _send(adapter, chat_id, PUBLIC_START_TEXT, keyboard)


async def _is_allowed(
    session: AsyncSession, platform: str, user_id: str
) -> bool:
    """Whether ``user_id`` may see the manager UI.

    When ``MANAGER_ACCESS_SECRET`` is empty the gate is disabled and everyone
    is allowed; otherwise the user must have unlocked the bot with
    ``/RSAsecret`` first.
    """
    if not get_settings().manager_access_secret:
        return True
    return await access_service.is_authorized(session, platform, user_id)


async def _handle_secret_command(
    session: AsyncSession,
    adapter: AbstractAdapter,
    platform: str,
    user_id: str,
    chat_id: str,
    text: str,
) -> None:
    """Unlock the manager UI when the correct secret is provided.

    Nothing is shown when the secret is wrong: the bot must not reveal that it
    exists to strangers.
    """
    expected = get_settings().manager_access_secret or "RSAsecret"
    parts = text.split()
    provided = parts[1] if len(parts) > 1 else SECRET_COMMAND.lstrip("/")
    if provided.casefold() != expected.casefold():
        logger.warning(
            "Rejected manager access attempt platform={} user={}", platform, user_id
        )
        return

    await user_service.get_or_create_user(session, platform, user_id)
    await access_service.grant_access(session, platform, user_id)
    log_user_event(platform, user_id, "access_granted")
    await _send(adapter, chat_id, WELCOME_TEXT, kb.main_menu())


async def handle_update(
    session: AsyncSession,
    adapter: AbstractAdapter,
    platform: str,
    update: dict[str, Any],
) -> None:
    """Route a single raw update to the correct handler."""
    if "callback_query" in update:
        await _handle_callback_update(
            session, adapter, platform, update["callback_query"]
        )
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

    chat_type = chat.get("type")

    # Groups are handled by the anonymous bot's reply/edit flows only.
    if chat_type in ("group", "supergroup"):
        await anon_bridge.handle_group_message(
            chat_id, user_id, text, str(msg.get("message_id", "")), msg
        )
        return

    # The manager UI only talks to *private* chats.  When the manager bot is
    # also a source-listening bot (same token, admin of the source channel)
    # channel posts arrive here too; they must never be answered as user
    # input (that would post replies into the channel).
    if chat_type is not None and chat_type != "private":
        return

    command: str | None = None
    if text.startswith("/"):
        command = text.split()[0].lower().split("@")[0]

        # The secret command unlocks the sync manager; /start is the public
        # anonymous-bot landing.  Both work before authorization.
        if command == SECRET_COMMAND:
            await _handle_secret_command(
                session, adapter, platform, user_id, chat_id, text
            )
            return
        if command == "/start":
            # Deep links (/start anon_TOKEN) continue the anonymous flow.
            if text.startswith("/start anon_"):
                await anon_bridge.handle_message(chat_id, user_id, text, msg)
            else:
                await _handle_public_start(adapter, chat_id)
            return

    # Sync-manager commands are gated behind /RSAsecret.
    if command in _SYNC_COMMANDS:
        if not await _is_allowed(session, platform, user_id):
            logger.info(
                "Ignored sync command from unauthorized user platform={} user={}",
                platform,
                user_id,
            )
            return
        user = await user_service.get_or_create_user(
            session, platform, user_id, sender.get("username")
        )
        await _handle_command(session, adapter, platform, user, chat_id, text)
        return

    # Everything else belongs to the public anonymous-message flows.  An
    # authorized admin in the middle of a sync conversation (e.g. waiting for
    # a channel id) keeps talking to the sync manager.
    if await _is_allowed(session, platform, user_id):
        user = await user_service.get_or_create_user(
            session, platform, user_id, sender.get("username")
        )
        ctx = state_machine.get(platform, user_id)
        if ctx.state != States.IDLE:
            await _handle_text(session, adapter, platform, user, chat_id, text, ctx)
            return

    await anon_bridge.handle_message(chat_id, user_id, text, msg)


async def _handle_callback_update(
    session: AsyncSession,
    adapter: AbstractAdapter,
    platform: str,
    cb: dict[str, Any],
) -> None:
    """Route a callback query to the anonymous bot or the sync manager."""
    data = cb.get("data") or ""
    cb_id = cb.get("id", "")
    sender = cb.get("from") or {}
    user_id = str(sender.get("id", ""))
    if not user_id:
        return
    cb_msg = cb.get("message") or {}
    chat_id = str(cb_msg.get("chat", {}).get("id", "") or user_id)
    message_id = str(cb_msg.get("message_id", "")) or None

    # Anonymous-bot buttons are public (no unlock required).
    if anon_bridge.is_anon_callback(data):
        await anon_bridge.handle_callback(data, cb_id, user_id, message_id, chat_id)
        return

    # Sync-manager buttons stay behind the gate.
    if not await _is_allowed(session, platform, user_id):
        return
    await _handle_callback(session, adapter, platform, cb)


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
    log_user_event(platform, user_id, "command", command=command)

    if command == "/start":
        state_machine.reset(platform, user_id)
        await _send(adapter, chat_id, WELCOME_TEXT, kb.main_menu())
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
        await _send(
            adapter,
            chat_id,
            "🎯 **تعیین کانال مبدأ**\n\n"
            "کانالی که می‌خوای پیام‌ها **ازش** خونده بشن رو انتخاب کن.\n\n"
            "📌 فقط کانال‌های بله و روبیکا می‌تونن مبدأ باشن.\n"
            "📌 ایتا فقط مقصد می‌تونه باشه.",
            kb.channel_picker(channels, kb.CHANNEL_PREFIX),
        )
    elif command == "/adddest":
        sources = await _channels_with_role(session, user.id, ChannelRole.SOURCE)
        if not sources:
            await _send(adapter, chat_id, "اول یک کانال مبدأ تعیین کنید. /setsource")
            return
        state_machine.set_state(platform, user_id, States.AWAIT_DEST_SELECT)
        await _send(
            adapter,
            chat_id,
            "🔗 **افزودن کانال مقصد**\n\n"
            "اول کانال مبدأ رو انتخاب کن، بعد کانال مقصد رو.\n\n"
            "📌 از این به بعد پیام‌های مبدأ به صورت خودکار توی مقصد منتشر می‌شن.",
            kb.channel_picker(sources, kb.CHANNEL_PREFIX),
        )
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
    elif command == "/settoken":
        # این رو خودت بر اساس پیاده‌سازی فعلی settoken پر کن،
        # اگه از قبل هست، این رو حذف کن.
        await _send(
            adapter,
            chat_id,
            "🔐 **ثبت توکن ربات**\n\n"
            "لطفاً توکن ربات رو به این شکل بفرست:\n"
            "`bale:TOKEN` یا `rubika:TOKEN` یا `eitaa:TOKEN`",
        )
    else:
        await _send(adapter, chat_id, "دستور ناشناخته. /help")


async def _cmd_mychannels(session, adapter, platform, user, chat_id) -> None:
    channels = await channel_service.list_channels(session, user.id)
    if not channels:
        await _send(adapter, chat_id, "هنوز کانالی ثبت نکرده‌اید. /addchannel")
        return
    await _send(
        adapter,
        chat_id,
        "📋 کانال‌های شما:\n\nبرای حذف هر کانال، دکمه «🗑 حذف» را بزنید.",
        kb.my_channels_keyboard(channels),
    )
    log_user_event(platform, user.platform_user_id, "mychannels", count=len(channels))


async def _cmd_links(session, adapter, platform, user, chat_id) -> None:
    links = await _list_links(session, user.id)
    if not links:
        await _send(adapter, chat_id, "هنوز لینکی نساخته‌اید. /adddest")
        return
    lines = ["لینک‌های همگام‌سازی:"]
    for link in links:
        state = "فعال" if link.is_active else "غیرفعال"
        src = link.source_channel.title or link.source_channel.platform_channel_id
        dst = link.destination_channel.title or link.destination_channel.platform_channel_id
        lines.append(f"• #{link.id}: {src} → {dst} — {state}")
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
async def _answer_callback_best_effort(
    adapter: AbstractAdapter,
    cb_id: str,
) -> None:
    """Acknowledge a callback query without ever breaking the button handler.

    Per the Bale docs (https://docs.bale.ai, ``answerCallbackQuery``):

    * The method must be called to clear the button's "waiting" state, but a
      failure to acknowledge must not prevent the button action from being
      processed (the update has already been consumed by the poller).
    * Clients older than Khordad 1404 do not support this feature: their
      ``callback_query_id`` starts with ``"1"``.  Calling the method for
      those ids is pointless (and can error), so we skip it.
    """
    if not cb_id:
        return
    if str(cb_id).startswith("1"):
        logger.debug("callback id {} is from an old client; skipping answerCallbackQuery", cb_id)
        return
    try:
        await adapter.answer_callback_query(cb_id)
    except AdapterError as exc:
        # Never let the acknowledgement failure kill the button handler.
        logger.warning("answerCallbackQuery failed (ignored): {}", exc)


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

    # Acknowledge first (fast UI feedback) but best-effort only.
    await _answer_callback_best_effort(adapter, cb_id)

    user = await user_service.get_or_create_user(session, platform, user_id, sender.get("username"))
    ctx = state_machine.get(platform, user_id)
    log_user_event(platform, user_id, "button", data=data)

    if data == kb.CANCEL or data == "cancel_del":
        state_machine.reset(platform, user_id)
        await _send(adapter, chat_id, "عملیات لغو شد.", kb.main_menu())
        return

    if data == "back_main":
        state_machine.reset(platform, user_id)
        await _send(adapter, chat_id, "منوی اصلی:", kb.main_menu())
        return

    if data.startswith("noop:"):
        # دکمه نمایشی، کاری نمی‌کند
        return

    if data.startswith("del_channel:"):
        try:
            channel_id = int(data.split(":", 1)[1])
        except ValueError:
            await _send(adapter, chat_id, "دکمه‌ای نامعتبر است. /mychannels")
            return
        await _on_delete_channel_requested(
            session, adapter, platform, user, chat_id, channel_id
        )
        return

    if data.startswith("confirm_del:"):
        try:
            channel_id = int(data.split(":", 1)[1])
        except ValueError:
            await _send(adapter, chat_id, "دکمه‌ای نامعتبر است. /mychannels")
            return
        await _on_delete_channel_confirmed(
            session, adapter, platform, user, chat_id, channel_id
        )
        return

    # Route main-menu buttons to their equivalent command handlers.
    if data in _CMD_ROUTES:
        await _handle_command(session, adapter, platform, user, chat_id, _CMD_ROUTES[data])
        return

    if data.startswith(kb.PLATFORM_PREFIX):
        chosen = data[len(kb.PLATFORM_PREFIX):]
        state_machine.set_state(
            platform, user_id, States.AWAIT_CHANNEL_ID, data={"channel_platform": chosen}
        )
        await _send(
            adapter,
            chat_id,
            f"🔹 **مرحله ۲ از ۳ — آیدی کانال {chosen}**\n\n"
            "آیدی کانال رو ارسال کن (عددی یا @username).\n\n"
            "📌 مثال: `@my_channel` یا `-1001234567890`\n"
            "⚠️ یادت نره ربات رو توی این کانال **ادمین** کنی.",
        )
        return

    if data.startswith(kb.CHANNEL_PREFIX):
        try:
            channel_id = int(data[len(kb.CHANNEL_PREFIX):])
        except ValueError:
            await _send(adapter, chat_id, "دکمه‌ای نامعتبر است. /start")
            return
        await _on_channel_selected(session, adapter, platform, user, chat_id, channel_id, ctx)
        return

    if data.startswith(kb.LINK_PREFIX):
        try:
            link_id = int(data[len(kb.LINK_PREFIX):])
        except ValueError:
            await _send(adapter, chat_id, "دکمه‌ای نامعتبر است. /start")
            return
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
        if not platform_supports_source(channel.platform):
            await _send(
                adapter,
                chat_id,
                f"⚠️ کانال {channel.platform} نمی‌تواند مبدأ باشد (فقط مقصد پشتیبانی می‌شود).",
            )
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
            if not dests:
                await _send(
                    adapter,
                    chat_id,
                    "هیچ کانال مقصدی ثبت نشده است. ابتدا با /addchannel "
                    "یک کانال مقصد اضافه کنید.",
                    kb.main_menu(),
                )
                state_machine.reset(platform, user.platform_user_id)
                return
            await _send(
                adapter,
                chat_id,
                "📥 حالا کانال **مقصد** رو انتخاب کن.\n\n"
                "پیام‌های مبدأ به این کانال منتقل می‌شن.",
                kb.channel_picker(dests, kb.CHANNEL_PREFIX),
            )
        else:
            source_id = int(ctx.data["source_id"])
            if source_id == channel_id:
                await _send(adapter, chat_id, "مبدأ و مقصد نمی‌توانند یکسان باشند.")
                return
            existing = await _find_link(session, user.id, source_id, channel_id)
            if existing is not None:
                await _send(
                    adapter,
                    chat_id,
                    f"⚠️ این لینک قبلاً ساخته شده است (لینک #{existing.id}). "
                    "با /links می‌توانید وضعیت آن را ببینید.",
                    kb.main_menu(),
                )
                state_machine.reset(platform, user.platform_user_id)
                return
            link = SyncLink(
                user_id=user.id,
                source_channel_id=source_id,
                destination_channel_id=channel_id,
            )
            session.add(link)
            await session.commit()
            cache_service.invalidate_links(source_id)
            state_machine.reset(platform, user.platform_user_id)
            log_user_event(
                platform, user.platform_user_id,
                "create_link", source_id=source_id, dest_id=channel_id,
            )
            await _send(
                adapter,
                chat_id,
                "🎉 **عالی! لینک همگام‌سازی ساخته شد.**\n\n"
                "از این به بعد هر پیامی توی کانال مبدأ بذاری،\n"
                "به صورت خودکار توی کانال مقصد هم منتشر می‌شه.\n\n"
                "💡 برای تست، یک پیام تستی توی کانال مبدأ بفرست.\n"
                "📌 برای مدیریت لینک‌ها از /links استفاده کن.",
                kb.main_menu(),
            )


async def _toggle_link(session, adapter, platform, user, chat_id, link_id) -> None:
    link = await session.get(SyncLink, link_id)
    if link is None or link.user_id != user.id:
        await _send(adapter, chat_id, "لینک یافت نشد.")
        return
    link.is_active = not link.is_active
    await session.commit()
    cache_service.invalidate_links()
    state = "فعال" if link.is_active else "غیرفعال"
    log_user_event(
        platform, user.platform_user_id, "toggle_link",
        link_id=link.id, active=link.is_active,
    )
    await _send(adapter, chat_id, f"لینک #{link.id} {state} شد.")


# ----------------------------------------------------------------------
# Text input (state-driven)
# ----------------------------------------------------------------------
def _normalize_channel_ref(raw: str) -> str:
    """Normalize a channel reference entered by the user.

    Accepts a full invite URL (``https://rubika.ir/foo``, ``ble.ir/foo``,
    ``eitaa.com/foo``, ``t.me/foo``, ...) as well as an ``@username`` or a
    numeric id, and returns a value the adapters can use as ``chat_id``.
    Platforms reject a full URL (Rubika: ``INVALID_INPUT``), so the URL is
    reduced to its last path segment and prefixed with ``@`` when needed.
    """
    value = raw.strip()
    lowered = value.lower()
    if "://" in lowered or lowered.startswith(
        ("rubika.ir/", "ble.ir/", "bale.ai/", "eitaa.com/", "t.me/")
    ):
        value = value.rstrip("/").split("/")[-1].split("?")[0]
        if value and not value.startswith("@"):
            value = "@" + value
    return value


async def _handle_text(
    session, adapter, platform, user, chat_id, text, ctx
) -> None:
    if ctx.state == States.AWAIT_CHANNEL_ID:
        chosen = ctx.data.get("channel_platform", platform)
        channel_ref = _normalize_channel_ref(text)
        title = channel_ref.lstrip("@")
        try:
            await channel_service.add_channel(
                session,
                user.id,
                ChannelCreate(
                    platform=chosen,
                    platform_channel_id=channel_ref,
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
            platform, user.platform_user_id, "addchannel", channel_platform=chosen, id=channel_ref
        )
        await _send(
            adapter,
            chat_id,
            "✅ **مرحله ۳ از ۳ — کانال ثبت شد!**\n\n"
            "⚠️ یادت نره ربات رو توی کانال **ادمین** کنی.\n\n"
            "💡 حالا می‌تونی:\n"
            "• با /setsource این کانال رو به عنوان مبدأ تعیین کنی\n"
            "• با /addchannel کانال مقصد رو اضافه کنی\n"
            "• با /mychannels لیست کانال‌هات رو ببینی",
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


async def _find_link(session, user_id, source_id, dest_id) -> SyncLink | None:
    """Return an existing link for this (user, source, destination) pair."""
    stmt = select(SyncLink).where(
        SyncLink.user_id == user_id,
        SyncLink.source_channel_id == source_id,
        SyncLink.destination_channel_id == dest_id,
    )
    return (await session.execute(stmt)).scalars().first()


async def _count(session, model, condition) -> int:
    stmt = select(func.count()).select_from(model).where(condition)
    return int((await session.execute(stmt)).scalar_one())

async def _on_delete_channel_requested(
    session, adapter, platform, user, chat_id, channel_id
) -> None:
    """Ask the user to confirm channel deletion."""
    channel = await channel_service.get_channel(session, channel_id, user.id)
    if channel is None:
        await _send(adapter, chat_id, "کانال یافت نشد یا متعلق به شما نیست.")
        return
    name = channel.title or channel.platform_channel_id
    await _send(
        adapter,
        chat_id,
        f"⚠️ آیا از حذف کانال «{name}» ({channel.platform}) مطمئن هستی؟\n\n"
        "با حذف این کانال، همه لینک‌های همگام‌سازی مرتبط با آن هم حذف می‌شوند.",
        kb.confirm_delete_keyboard(channel_id),
    )


async def _on_delete_channel_confirmed(
    session, adapter, platform, user, chat_id, channel_id
) -> None:
    """Delete a channel after user confirmation."""
    channel = await channel_service.get_channel(session, channel_id, user.id)
    if channel is None:
        await _send(adapter, chat_id, "کانال یافت نشد یا متعلق به شما نیست.")
        return
    name = channel.title or channel.platform_channel_id
    ch_platform = channel.platform
    ok = await channel_service.delete_channel(session, channel_id, user.id)
    if not ok:
        await _send(adapter, chat_id, "حذف ناموفق بود.")
        return
    cache_service.invalidate_channel(ch_platform)
    cache_service.invalidate_links()
    state_machine.reset(platform, user.platform_user_id)
    log_user_event(
        platform, user.platform_user_id, "delete_channel",
        channel_id=channel_id, name=name,
    )
    await _send(
        adapter,
        chat_id,
        f"✅ کانال «{name}» با موفقیت حذف شد.",
        kb.main_menu(),
    )
