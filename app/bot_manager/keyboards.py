"""Inline keyboard builders for the manager bot."""

from __future__ import annotations

from app.adapters import InlineKeyboardButton, InlineKeyboardMarkup
from app.models import Channel, SyncLink
from app.models.channel import ChannelRole

# Bale (like Telegram) caps inline button labels at 64 characters; longer
# labels make the whole sendMessage request fail, so truncate defensively.
MAX_BUTTON_TEXT = 64


def _clamp(text: str) -> str:
    """Truncate ``text`` to the platform button-label limit."""
    if len(text) <= MAX_BUTTON_TEXT:
        return text
    return text[: MAX_BUTTON_TEXT - 1] + "…"

# Callback data prefixes
CMD_ADDCHANNEL = "cmd:addchannel"
CMD_MYCHANNELS = "cmd:mychannels"
CMD_SETSOURCE = "cmd:setsource"
CMD_ADDDEST = "cmd:adddest"
CMD_LINKS = "cmd:links"
CMD_PAUSE = "cmd:pause"
CMD_STATUS = "cmd:status"
PLATFORM_PREFIX = "platform:"
CHANNEL_PREFIX = "channel:"
LINK_PREFIX = "link:"
CANCEL = "cmd:cancel"


def main_menu() -> InlineKeyboardMarkup:
    """Return the main menu keyboard."""
    rows = [
        [InlineKeyboardButton(text="➕ افزودن کانال", callback_data=CMD_ADDCHANNEL)],
        [InlineKeyboardButton(text="📋 کانال‌های من", callback_data=CMD_MYCHANNELS)],
        [
            InlineKeyboardButton(text="🎯 تعیین مبدأ", callback_data=CMD_SETSOURCE),
            InlineKeyboardButton(text="🔗 افزودن مقصد", callback_data=CMD_ADDDEST),
        ],
        [InlineKeyboardButton(text="🔁 لینک‌ها", callback_data=CMD_LINKS)],
        [
            InlineKeyboardButton(text="⏸ توقف/ادامه", callback_data=CMD_PAUSE),
            InlineKeyboardButton(text="📊 وضعیت", callback_data=CMD_STATUS),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def platform_picker() -> InlineKeyboardMarkup:
    """Return a keyboard to pick a platform."""
    rows = [
        [
            InlineKeyboardButton(text="بله", callback_data=f"{PLATFORM_PREFIX}bale"),
            InlineKeyboardButton(text="ایتا", callback_data=f"{PLATFORM_PREFIX}eitaa"),
            InlineKeyboardButton(text="روبیکا", callback_data=f"{PLATFORM_PREFIX}rubika"),
        ],
        [InlineKeyboardButton(text="انصراف", callback_data=CANCEL)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def channel_picker(channels: list[Channel], prefix: str) -> InlineKeyboardMarkup:
    """Return a keyboard listing channels as selectable buttons."""
    rows = [
        [
            InlineKeyboardButton(
                text=_clamp(f"{c.title or c.platform_channel_id} ({c.platform})"),
                callback_data=f"{prefix}{c.id}",
            )
        ]
        for c in channels
    ]
    rows.append([InlineKeyboardButton(text="انصراف", callback_data=CANCEL)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def my_channels_keyboard(channels: list[Channel]) -> InlineKeyboardMarkup:
    """Return a keyboard listing the user's channels with a delete button."""
    rows = []
    for c in channels:
        role = "مبدأ" if c.role == ChannelRole.SOURCE else "مقصد"
        rows.append([
            InlineKeyboardButton(
                text=_clamp(f"{c.title or c.platform_channel_id} ({c.platform}) — {role}"),
                callback_data=f"noop:{c.id}",
            ),
            InlineKeyboardButton(
                text="🗑 حذف",
                callback_data=f"del_channel:{c.id}",
            ),
        ])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_delete_keyboard(channel_id: int) -> InlineKeyboardMarkup:
    """Return a yes/no confirmation keyboard for channel deletion."""
    rows = [
        [
            InlineKeyboardButton(
                text="✅ بله، حذف کن",
                callback_data=f"confirm_del:{channel_id}",
            ),
            InlineKeyboardButton(
                text="❌ انصراف",
                callback_data="cancel_del",
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def link_picker(links: list[SyncLink]) -> InlineKeyboardMarkup:
    """Return a keyboard listing sync links as toggle buttons."""
    rows = []
    for link in links:
        state = "✅" if link.is_active else "⏸"
        src = link.source_channel.title or link.source_channel_id
        dst = link.destination_channel.title or link.destination_channel_id
        rows.append(
            [
                InlineKeyboardButton(
                    text=_clamp(f"{state} {link.id}: {src} → {dst}"),
                    callback_data=f"{LINK_PREFIX}{link.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="انصراف", callback_data=CANCEL)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
