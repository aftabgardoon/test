"""
سیستم لینک ناشناس جدید
قابلیت‌ها:
- ساخت چندین لینک با اسم‌های مختلف
- نام نمایشی برای فرستنده
- ویرایش و حذف پیام توسط فرستنده
- منسوخ کردن و تمدید لینک
"""
from helpers import send_permanent, send, api_call, send_any_media, delete_message, answer_callback, edit_inline_menu
from config import BASE_URL
from logger import info, error_log
import requests

# ⭐ گرفتن username بات - فقط یکبار اجرا میشه
_bot_username = None

def _get_bot_username():
    """دریافت username بات از API بله"""
    global _bot_username
    if _bot_username:
        return _bot_username

    try:
        result = api_call("getMe")
        if result.get("ok"):
            username = result.get("result", {}).get("username", "")
            if username:
                _bot_username = username
                return _bot_username
    except:
        pass

    _bot_username = "Meshkat8_bot"
    return _bot_username


# ==================== پنل اصلی ====================
def show_anonymous_panel(chat_id, user_id, message_id=None):
    """نمایش پنل مدیریت لینک‌های ناشناس"""
    from database import get_user_anonymous_links, get_user_display_name

    links = get_user_anonymous_links(user_id)
    display_name = get_user_display_name(user_id)

    text = "👻 *لینک‌های ناشناس شما*\n\n"

    if display_name:
        text += f"📝 نام نمایشی: *{display_name}*\n\n"
    else:
        text += "📝 نام نمایشی: ❌ تنظیم نشده\n\n"

    if links:
        text += "📋 *لینک‌های فعال:*\n"
        for link in links:
            bot_username = _get_bot_username()
            link_url = f"https://ble.ir/{bot_username}?start=anon_{link['token']}"
            status = "🟢" if link['is_active'] else "🔴"
            text += f"\n{status} *{link['link_name']}*\n"
            text += f"{link_url}\n"

        text += "\n👆 روی لینک‌ها کلیک کن یا برای دوستات بفرست"
    else:
        text += "📋 *هیچ لینکی نساختی!*\n\n➕ یه لینک جدید بساز تا دوستات ناشناس بهت پیام بدن."

    # ساخت دکمه‌ها
    keyboard = []

    # دکمه‌های مدیریت لینک‌ها
    if links:
        keyboard.append([{"text": "📋 لیست و مدیریت لینک‌ها", "callback_data": "anol_list"}])

    # ⭐ محدودیت تعداد لینک‌ها (حداکثر ۲۰ عدد)
    if len(links) >= 20:
        keyboard.append([{"text": "⛔ تعداد لینک‌ها به حداکثر رسیده (۲۰ عدد)", "callback_data": "no_action"}])
    else:
        keyboard.append([{"text": "➕ ساخت لینک جدید", "callback_data": "anol_new"}])

    # دکمه نام نمایشی
    if display_name:
        keyboard.append([{"text": "✏️ تغییر نام نمایشی", "callback_data": "anol_dname"}])
    else:
        keyboard.append([{"text": "✏️ تنظیم نام نمایشی", "callback_data": "anol_dname"}])

    # ⭐ دکمه کپی لینک‌ها
    if links:
        keyboard.append([{"text": "📋 کپی لینک‌ها", "callback_data": "anol_copylist"}])

    keyboard.append([{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "m_main"}])

    if message_id:
        try:
            requests.post(f"{BASE_URL}editMessageText", json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "reply_markup": {"inline_keyboard": keyboard},
                "parse_mode": "Markdown"
            }, timeout=5)
        except:
            api_call("sendMessage", json_data={
                "chat_id": chat_id,
                "text": text,
                "reply_markup": {"inline_keyboard": keyboard}
            })
    else:
        api_call("sendMessage", json_data={
            "chat_id": chat_id,
            "text": text,
            "reply_markup": {"inline_keyboard": keyboard}
        })

def show_anonymous_links_list_panel(chat_id, user_id, message_id=None):
    """نمایش لیست لینک‌های ناشناس با دکمه ورود به مدیریت هر لینک"""
    from database import get_user_anonymous_links
    from helpers import edit_inline_menu, send_inline_keyboard

    links = get_user_anonymous_links(user_id)

    if not links:
        text = "📋 *لیست لینک‌های ناشناس*\n\n❌ هنوز هیچ لینکی نساختی!\n\n➕ از دکمه زیر برای ساخت لینک جدید استفاده کن."
        buttons = [
            [{"text": "➕ ساخت لینک جدید", "callback_data": "anol_new"}],
            [{"text": "🔙 بازگشت", "callback_data": "anol_back"}]
        ]
        if message_id:
            edit_inline_menu(chat_id, message_id, text, buttons)
        else:
            send_inline_keyboard(chat_id, text, buttons)
        return

    text = "📋 *لیست لینک‌های ناشناس*\n\n"
    text += f"📊 تعداد: {len(links)} لینک\n\n"
    text += "👇 روی هر لینک کلیک کن تا وارد مدیریت اون بشی:\n\n"

    buttons = []
    for link in links:
        link_id = link["id"]
        link_name = link["link_name"]
        is_active = link["is_active"]
        status = "🟢" if is_active else "🔴"
        text += f"{status} *{link_name}*\n"
        if link.get("group_id") and link["group_id"] != 0:
            text += f"👥 گروه: {link.get('group_title', 'نامشخص')}\n"
        if link.get("channel_id") and link["channel_id"] != 0:
            text += f"📢 کانال: {link.get('channel_title', 'نامشخص')}\n"
        text += "\n"

        buttons.append([
            {"text": f"{status} {link_name}", "callback_data": f"anol_manage_{link_id}"}
        ])

    buttons.append([{"text": "➕ ساخت لینک جدید", "callback_data": "anol_new"}])
    buttons.append([{"text": "🔙 بازگشت", "callback_data": "anol_back"}])

    if message_id:
        edit_inline_menu(chat_id, message_id, text, buttons)
    else:
        send_inline_keyboard(chat_id, text, buttons)

def show_manage_panel(chat_id, user_id, message_id=None, link_id=None):
    """نمایش پنل مدیریت لینک‌ها (اگر link_id مشخص باشه، فقط اون لینک رو نشون بده)"""
    from database import get_user_anonymous_links

    links = get_user_anonymous_links(user_id)

    # اگر link_id مشخص شده، فقط اون لینک رو نشون بده
    if link_id:
        for link in links:
            if link["id"] == link_id:
                return show_manage_single_panel(chat_id, user_id, link, message_id)
        send(chat_id, "❌ لینک پیدا نشد!")
        return

    links = get_user_anonymous_links(user_id)

    if not links:
        # برگشت به پنل اصلی
        show_anonymous_panel(chat_id, user_id, message_id)
        return

    text = "📋 *مدیریت لینک‌های ناشناس*\n\n"
    text += "برای منسوخ کردن یا تمدید، روی لینک کلیک کن:\n"

    keyboard = []
    for link in links:
        status = "🟢 فعال" if link['is_active'] else "🔴 منسوخ"
        text += f"\n• *{link['link_name']}* ({status})"

        # ⭐ ردیف ۰: اسم لینک (no_action)
        status_emoji = "🟢" if link['is_active'] else "🔴"
        keyboard.append([
            {"text": f"{status_emoji} {link['link_name']} :", "callback_data": f"anol_sec_{link['id']}"}
        ])

        # ردیف ۱: غیرفعال کردن/تمدید/حذف (ایموجی بر اساس وضعیت فعلی)
        row_actions = []
        if link['is_active']:
            row_actions.append({"text": f"🟢 غیرفعال کردن", "callback_data": f"anol_deact_{link['id']}"})
        else:
            row_actions.append({"text": f"🔴 فعال کردن", "callback_data": f"anol_reactivate_{link['id']}"})
        row_actions.append({"text": f"🔄 تمدید", "callback_data": f"anol_renew_{link['id']}"})
        keyboard.append(row_actions)

        # ردیف حذف (برای همه لینک‌ها - چه فعال چه غیرفعال)
        keyboard.append([
            {"text": f"🗑️ حذف کامل لینک", "callback_data": f"anol_delete_{link['id']}"}
        ])

        # ردیف ۲: تنظیم گروه
        group_id = link.get('group_id', 0)
        group_title = link.get('group_title', '')
        if group_id:
            display_name = group_title if group_title else str(group_id)
            keyboard.append([
                {"text": f"👥 گروه: {display_name} (حذف)", "callback_data": f"anol_nogroup_{link['id']}"}
            ])
        else:
            keyboard.append([
                {"text": f"👥 تنظیم گروه", "callback_data": f"anol_setgroup_{link['id']}"}
            ])

        # ردیف ۳: تنظیم کانال
        channel_id = link.get('channel_id', 0)
        channel_title = link.get('channel_title', '')
        if channel_id:
            display_ch = channel_title if channel_title else str(channel_id)
            keyboard.append([
                {"text": f"📢 کانال: {display_ch} (حذف)", "callback_data": f"anol_nochannel_{link['id']}"}
            ])
        else:
            keyboard.append([
                {"text": f"📢 تنظیم کانال", "callback_data": f"anol_setchannel_{link['id']}"}
            ])

    keyboard.append([{"text": "🔙 بازگشت", "callback_data": "anol_back"}])

    if message_id:
        try:
            requests.post(f"{BASE_URL}editMessageText", json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "reply_markup": {"inline_keyboard": keyboard},
                "parse_mode": "Markdown"
            }, timeout=5)
        except:
            api_call("sendMessage", json_data={
                "chat_id": chat_id,
                "text": text,
                "reply_markup": {"inline_keyboard": keyboard}
            })
    else:
        api_call("sendMessage", json_data={
            "chat_id": chat_id,
            "text": text,
            "reply_markup": {"inline_keyboard": keyboard}
        })

def show_manage_single_panel(chat_id, user_id, link, message_id=None):
    """نمایش پنل مدیریت برای یک لینک ناشناس خاص (ترتیب مثل صندلی داغ)"""
    from helpers import edit_inline_menu, send_inline_keyboard

    link_id = link["id"]
    link_name = link["link_name"]
    is_active = link["is_active"]
    group_id = link.get("group_id", 0)
    group_title = link.get("group_title", "")
    channel_id = link.get("channel_id", 0)
    channel_title = link.get("channel_title", "")

    status_text = "فعال" if is_active else "غیرفعال"
    status_emoji = "🟢" if is_active else "🔴"

    text = f"🔧 *مدیریت لینک: {link_name}*\n\n"
    text += f"📊 وضعیت: {status_emoji} {status_text}\n"
    if group_id and group_id != 0:
        text += f"👥 گروه: {group_title}\n"
    if channel_id and channel_id != 0:
        text += f"📢 کانال: {channel_title}\n"
    text += "\n━━━━━━━━━━━━━━━━━━\n"

    buttons = []

    # ردیف ۱: فعال/غیرفعال + تمدید (مثل صندلی داغ)
    if is_active:
        buttons.append([{"text": "🟢 غیرفعال کردن", "callback_data": f"anol_deact_{link_id}"}])
    else:
        buttons.append([{"text": "🔴 فعال کردن", "callback_data": f"anol_reactivate_{link_id}"}])
    # دکمه تمدید (مثل صندلی داغ)
    buttons.append([{"text": "🔄 تمدید لینک", "callback_data": f"anol_renew_{link_id}"}])

    # ردیف ۲: حذف کامل (مثل صندلی داغ)
    buttons.append([{"text": "🗑️ حذف کامل لینک", "callback_data": f"anol_delete_{link_id}"}])

    # ردیف ۳: تنظیم گروه (مثل کانال صندلی داغ)
    if group_id and group_id != 0:
        buttons.append([{"text": f"👥 گروه: {group_title} (تغییر)", "callback_data": f"anol_setgroup_{link_id}"}])
    else:
        buttons.append([{"text": "👥 تنظیم گروه", "callback_data": f"anol_setgroup_{link_id}"}])

    # ردیف ۴: تنظیم کانال (مثل کانال صندلی داغ)
    if channel_id and channel_id != 0:
        buttons.append([{"text": f"📢 کانال: {channel_title} (تغییر)", "callback_data": f"anol_setchannel_{link_id}"}])
    else:
        buttons.append([{"text": "📢 تنظیم کانال", "callback_data": f"anol_setchannel_{link_id}"}])

    # ردیف ۵: امنیت + لیست بلاکی
    from database import conn as db_conn
    cur = db_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM anonymous_link_blocks WHERE link_id = ?", (link_id,))
    block_count = cur.fetchone()[0]

    buttons.append([
        {"text": f"🛡️ تنظیمات امنیتی", "callback_data": f"anol_sec_{link_id}"},
        {"text": f"🚫 لیست بلاکی ({block_count})", "callback_data": f"anol_blocklist_{link_id}"}
    ])

    # ردیف ۶: بازگشت به لیست (مثل صندلی داغ)
    buttons.append([{"text": "🔙 بازگشت به لیست لینک‌ها", "callback_data": "anol_list"}])

    if message_id:
        edit_inline_menu(chat_id, message_id, text, buttons)
    else:
        send_inline_keyboard(chat_id, text, buttons)

def show_anonymous_messages_panel(chat_id, user_id, link_id=None, message_id=None):
    """نمایش لیست پیام‌های دریافت شده (مثل سوالات صندلی داغ)"""
    from database import conn as db_conn

    cur = db_conn.cursor()

    if link_id:
        cur.execute("""
            SELECT id, message, created_at
            FROM anonymous_messages
            WHERE link_id = ?
            ORDER BY id DESC
            LIMIT 20
        """, (link_id,))
    else:
        cur.execute("""
            SELECT am.id, am.message, am.created_at, al.link_name
            FROM anonymous_messages am
            JOIN anonymous_links al ON am.link_id = al.id
            WHERE al.owner_id = ?
            ORDER BY am.id DESC
            LIMIT 20
        """, (user_id,))
    messages = cur.fetchall()

    if not messages:
        text = "📋 *پیام‌های دریافت شده*\n\n❌ هنوز پیامی دریافت نشده!"
        keyboard = [[{"text": "🔙 بازگشت", "callback_data": "anol_back"}]]
    else:
        text = "📋 *پیام‌های دریافت شده*\n\n"
        text += "👇 روی هر پیام کلیک کن:\n\n"

        keyboard = []
        for msg in messages:
            if link_id:
                msg_id, msg_text, created_at = msg
                link_name = ""
            else:
                msg_id, msg_text, created_at, link_name = msg

            preview = msg_text[:35] + "..." if len(msg_text) > 35 else msg_text
            label = f"💬 {preview}"
            if link_name:
                label += f" [{link_name}]"

            keyboard.append([
                {"text": label, "callback_data": f"anol_msg_{msg_id}"}
            ])

        keyboard.append([{"text": "🔙 بازگشت", "callback_data": "anol_back"}])

    if message_id:
        try:
            requests.post(f"{BASE_URL}editMessageText", json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "reply_markup": {"inline_keyboard": keyboard},
                "parse_mode": "Markdown"
            }, timeout=5)
        except:
            api_call("sendMessage", json_data={
                "chat_id": chat_id,
                "text": text,
                "reply_markup": {"inline_keyboard": keyboard}
            })
    else:
        api_call("sendMessage", json_data={
            "chat_id": chat_id,
            "text": text,
            "reply_markup": {"inline_keyboard": keyboard}
        })

def show_anonymous_message_detail(chat_id, user_id, msg_id, message_id=None):
    """نمایش جزئیات یک پیام ناشناس"""
    from database import conn as db_conn

    cur = db_conn.cursor()
    cur.execute("""
        SELECT am.id, am.message, am.created_at, al.link_name, am.from_user_id
        FROM anonymous_messages am
        JOIN anonymous_links al ON am.link_id = al.id
        WHERE am.id = ? AND al.owner_id = ?
    """, (msg_id, user_id))
    row = cur.fetchone()

    if not row:
        send(chat_id, "❌ پیام پیدا نشد!")
        return

    msg_id, msg_text, created_at, link_name, from_user_id = row

    from helpers import get_user_name
    from database import get_user_display_name
    sender_name = get_user_display_name(from_user_id) or get_user_name(from_user_id) or f"کاربر {from_user_id}"

    text = f"📝 *جزئیات پیام ناشناس*\n\n"
    text += f"🔗 لینک: {link_name}\n"
    text += f"👤 فرستنده: {sender_name}\n"
    text += f"📅 تاریخ: {created_at}\n\n"
    text += f"📄 *متن پیام:*\n{msg_text}\n"

    buttons = [
        [{"text": "↩️ پاسخ", "callback_data": f"alink_reply_{msg_id}_{from_user_id}"}],
        [{"text": "🔙 بازگشت", "callback_data": "anol_messages"}]
    ]

    if message_id:
        edit_inline_menu(chat_id, message_id, text, buttons)
    else:
        send_inline_keyboard(chat_id, text, buttons)

# ==================== هندلرهای اصلی ====================

def handle_anonymous_link(chat_id, user_id, text, msg=None):
    """هندلر دکمه لینک ناشناس"""
    if text == "🔗 لینک ناشناس" or text == "لینک ناشناس":
        show_anonymous_panel(chat_id, user_id)
        return True
    return False


def handle_anonymous_start(chat_id, user_id, text, msg=None):
    """پردازش /start anon_TOKEN - ورود از لینک ناشناس جدید"""
    if not text:
        return False

    # ⭐ تشخیص لینک جدید (anon_ + توکن)
    if text.startswith("/start anon_") and len(text) > len("/start anon_"):
        token = text.replace("/start anon_", "").strip()

        # ⭐ چک کن توکن ۱۲ کاراکتری هست یا عددی (قدیمی)
        if token.isdigit():
            # لینک قدیمی - پردازش توسط سیستم قدیمی
            return handle_anonymous_start_old(chat_id, user_id, text, msg)

        # ⭐ لینک جدید - پردازش با توکن
        from database import get_anonymous_link_by_token
        link_info = get_anonymous_link_by_token(token)

        if not link_info:
            send(chat_id, "❌ لینک نامعتبره!")
            return True

        if not link_info['is_active']:
            send(chat_id, "❌ این لینک منسوخ شده!\n📌 از صاحب لینک بخواه یه لینک جدید بده.")
            return True

        # ⭐ تنظیم reply_waiting برای دریافت پیام
        from state import reply_waiting
        reply_waiting[user_id] = {
            "type": "anonymous_link_new",
            "target": link_info['owner_id'],
            "link_id": link_info['id'],
            "link_name": link_info['link_name']
        }

        # ⭐ گرفتن نام نمایشی صاحب لینک
        from database import get_user_display_name
        owner_display_name = get_user_display_name(link_info['owner_id'])
        from helpers import get_user_name
        owner_real_name = get_user_name(link_info['owner_id']) or f"کاربر {link_info['owner_id']}"
        owner_info = f"*{owner_display_name}*" if owner_display_name else f"*{owner_real_name}*"

        # ⭐ تنظیم reply_waiting
        from state import reply_waiting
        reply_waiting[user_id] = {
            "type": "anonymous_link_new",
            "target": link_info['owner_id'],
            "link_id": link_info['id'],
            "link_name": link_info['link_name']
        }

        # ⭐ پیام توضیحی در چت (بدون Alert)
        keyboard = {
            "inline_keyboard": [[{"text": "❌ لغو", "callback_data": "cancel_waiting"}]]
        }
        api_call("sendMessage", json_data={
            "chat_id": chat_id,
            "text": f"👻 *پیام ناشناس*\n\n📎 شما در حال ارسال پیام ناشناس به *{owner_info}* هستید\n✏️ پیامت رو بنویس و بفرست",
            "reply_markup": keyboard
        })

        info(f"🔗 کاربر {user_id} از لینک '{link_info['link_name']}' وارد شد")
        return True

    # ⭐ تشخیص لینک قدیمی (/start anon_USERID)
    elif text.startswith("/start anon_"):
        return handle_anonymous_start_old(chat_id, user_id, text, msg)

    return False


def handle_anonymous_start_old(chat_id, user_id, text, msg=None):
    """پردازش لینک قدیمی (anon_USERID) - برای سازگاری با قبل"""
    try:
        target_id = int(text.replace("/start anon_", "").strip())

        from state import reply_waiting
        reply_waiting[user_id] = {"type": "anonymous_link", "id": 0, "target": target_id}
        return True
    except:
        send(chat_id, "❌ لینک نامعتبره!")
        return True


def handle_anonymous_link_reply(chat_id, user_id, text, msg=None):
    """پردازش ارسال پیام از لینک ناشناس (جدید و قدیمی)"""
    from state import reply_waiting
    from helpers import send_any_media

    if user_id not in reply_waiting:
        return False

    wait_info = reply_waiting[user_id]
    wait_type = wait_info.get("type", "")

    # ⭐ پردازش لینک جدید
    if wait_type == "anonymous_link_new":
        return _handle_new_link_reply(chat_id, user_id, text, msg, wait_info)

    # ⭐ پردازش لینک قدیمی
    elif wait_type == "anonymous_link":
        return _handle_old_link_reply(chat_id, user_id, text, msg, wait_info)

    # ⭐ چت ناشناس از تله (کاملاً جدا)
    elif wait_type == "trap_anon":
        return _handle_trap_anon_reply(chat_id, user_id, text, msg, wait_info)

    return False


def _handle_new_link_reply(chat_id, user_id, text, msg, wait_info):
    """پردازش پیام از لینک جدید"""
    from state import reply_waiting
    from database import conn as db_conn, get_user_display_name, is_user_blocked

    if text in ["لغو", "انصراف", "/cancel", "cancel"]:
        del reply_waiting[user_id]
        send(chat_id, "❌ ارسال پیام ناشناس لغو شد.")
        return True

    target_id = wait_info["target"]
    link_id = wait_info["link_id"]
    link_name = wait_info["link_name"]

    # ⭐⭐⭐ چک محتوای پیام ناشناس (NSFW، خشونت، فحش) ⭐⭐⭐
    if msg:
        from database import is_nsfw_enabled, is_badwords_enabled
        from handlers.safety_filter import is_gore_enabled as _is_gore

        # فقط برای صاحب لینک چک کن (target_id)
        # چک NSFW
        from database import get_anonymous_link_security
        link_security = get_anonymous_link_security(link_id)
        if link_security.get('anti_nsfw', False) and (msg.get("photo") or msg.get("video") or msg.get("animation")):
            try:
                import os, time as _time
                from database import conn as _conn

                file_id = None
                file_unique_id = None
                if msg.get("photo"):
                    file_id = msg["photo"][-1]["file_id"]
                    file_unique_id = msg["photo"][-1].get("file_unique_id", file_id)
                elif msg.get("video"):
                    file_id = msg["video"]["file_id"]
                    file_unique_id = msg["video"].get("file_unique_id", file_id)
                elif msg.get("animation"):
                    file_id = msg["animation"]["file_id"]
                    file_unique_id = msg["animation"].get("file_unique_id", file_id)

                if file_id and file_unique_id:
                    # ⭐ چک کش
                    cur = _conn.cursor()
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS nsfw_cache (
                            file_unique_id TEXT PRIMARY KEY,
                            nsfw_score REAL,
                            is_nsfw INTEGER DEFAULT 0,
                            gore_score REAL,
                            is_gore INTEGER DEFAULT 0,
                            first_checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            check_count INTEGER DEFAULT 1
                        )
                    """)
                    _conn.commit()

                    cur.execute(
                        "SELECT nsfw_score, is_nsfw FROM nsfw_cache WHERE file_unique_id = ?",
                        (file_unique_id,)
                    )
                    cached = cur.fetchone()

                    if cached:
                        nsfw_score, is_nsfw = cached
                        cur.execute(
                            "UPDATE nsfw_cache SET last_checked_at = CURRENT_TIMESTAMP, check_count = check_count + 1 WHERE file_unique_id = ?",
                            (file_unique_id,)
                        )
                        _conn.commit()

                        if is_nsfw and nsfw_score and nsfw_score > 0.7:
                            del reply_waiting[user_id]
                            send(chat_id, "⛔ محتوای نامناسب (+18) قابل ارسال نیست. (کش)")
                            return True
                    else:
                        # ⭐ دانلود و بررسی جدید
                        file_info = requests.get(f"{BASE_URL}getFile?file_id={file_id}").json()
                        file_path = file_info.get("result", {}).get("file_path", "")
                        if file_path:
                            download_url = f"https://tapi.bale.ai/file/bot262177859:Yln_PupSbSxRmopfmgYhUI1c1VaNWt2CmLU/{file_path}"
                            temp_dir = os.path.join(os.path.dirname(__file__), "..", "temp")
                            os.makedirs(temp_dir, exist_ok=True)
                            local_path = os.path.join(temp_dir, f"anon_nsfw_{user_id}_{_time.time()}.jpg")
                            r = requests.get(download_url, timeout=30)
                            with open(local_path, 'wb') as f:
                                f.write(r.content)

                            from dataset.nsfw_detector import check_nsfw_score
                            score = check_nsfw_score(local_path)

                            # ⭐ ذخیره در کش
                            is_nsfw_flag = 1 if score > 0.7 else 0
                            cur.execute("""
                                INSERT OR REPLACE INTO nsfw_cache
                                (file_unique_id, nsfw_score, is_nsfw, first_checked_at, last_checked_at, check_count)
                                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
                            """, (file_unique_id, score, is_nsfw_flag))
                            _conn.commit()

                            try:
                                os.remove(local_path)
                            except:
                                pass

                            if score > 0.7:
                                del reply_waiting[user_id]
                                send(chat_id, "⛔ محتوای نامناسب (+18) قابل ارسال نیست. پیام شما حذف شد.")
                                return True
            except:
                pass

        # چک فحش (فقط لیست - تشخیص کلمه کامل و جدا)
        if link_security.get('anti_badwords', False) and text:
            import os
            import re
            badwords_file = os.path.join(os.path.dirname(__file__), "..", "data", "badwords.txt")
            is_bad = False
            try:
                with open(badwords_file, "r", encoding="utf-8") as f:
                    badwords_list = [line.strip().lower() for line in f if line.strip()]

                text_lower = text.lower()
                for badword in badwords_list:
                    # ⭐ کلمه باید به صورت کامل و جدا باشه
                    pattern = r'(?:^|\s|[،\.\!\؟\;\:\(\)\[\]\{\}])' + re.escape(badword) + r'(?=\s|$|[،\.\!\؟\;\:\(\)\[\]\{\}])'
                    if re.search(pattern, text_lower):
                        is_bad = True
                        break
            except:
                pass

            if is_bad:
                del reply_waiting[user_id]
                send(chat_id, "⛔ پیام شما حاوی کلمات نامناسب است و ارسال نشد.")
                return True

        # چک خشونت
        if link_security.get('anti_gore', False) and (msg.get("photo") or msg.get("video")):
            try:
                import os, time as _time
                from database import conn as _conn

                file_id = None
                file_unique_id = None
                if msg.get("photo"):
                    file_id = msg["photo"][-1]["file_id"]
                    file_unique_id = msg["photo"][-1].get("file_unique_id", file_id)
                elif msg.get("video"):
                    file_id = msg["video"]["file_id"]
                    file_unique_id = msg["video"].get("file_unique_id", file_id)

                if file_id and file_unique_id:
                    # ⭐ چک کش
                    cur = _conn.cursor()
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS nsfw_cache (
                            file_unique_id TEXT PRIMARY KEY,
                            nsfw_score REAL,
                            is_nsfw INTEGER DEFAULT 0,
                            gore_score REAL,
                            is_gore INTEGER DEFAULT 0,
                            first_checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            check_count INTEGER DEFAULT 1
                        )
                    """)
                    _conn.commit()

                    cur.execute(
                        "SELECT gore_score, is_gore FROM nsfw_cache WHERE file_unique_id = ?",
                        (file_unique_id,)
                    )
                    cached = cur.fetchone()

                    if cached:
                        gore_score, is_gore = cached
                        cur.execute(
                            "UPDATE nsfw_cache SET last_checked_at = CURRENT_TIMESTAMP, check_count = check_count + 1 WHERE file_unique_id = ?",
                            (file_unique_id,)
                        )
                        _conn.commit()

                        if is_gore and gore_score and gore_score > 0.4:
                            del reply_waiting[user_id]
                            send(chat_id, "⛔ محتوای خشونت‌آمیز قابل ارسال نیست. (کش)")
                            return True
                    else:
                        # ⭐ دانلود و بررسی جدید
                        file_info = requests.get(f"{BASE_URL}getFile?file_id={file_id}").json()
                        file_path = file_info.get("result", {}).get("file_path", "")
                        if file_path:
                            download_url = f"https://tapi.bale.ai/file/bot262177859:Yln_PupSbSxRmopfmgYhUI1c1VaNWt2CmLU/{file_path}"
                            temp_dir = os.path.join(os.path.dirname(__file__), "..", "temp")
                            os.makedirs(temp_dir, exist_ok=True)
                            ext = ".mp4" if msg.get("video") else ".jpg"
                            local_path = os.path.join(temp_dir, f"anon_gore_{user_id}_{_time.time()}{ext}")
                            r = requests.get(download_url, timeout=30)
                            with open(local_path, 'wb') as f:
                                f.write(r.content)

                            from dataset.gore_vit_detector import check_gore_score_from_path
                            score = check_gore_score_from_path(local_path)

                            # ⭐ ذخیره در کش
                            is_gore_flag = 1 if score > 0.4 else 0
                            cur.execute("""
                                INSERT OR REPLACE INTO nsfw_cache
                                (file_unique_id, gore_score, is_gore, first_checked_at, last_checked_at, check_count)
                                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
                            """, (file_unique_id, score, is_gore_flag))
                            _conn.commit()

                            try:
                                os.remove(local_path)
                            except:
                                pass

                            if score > 0.4:
                                del reply_waiting[user_id]
                                send(chat_id, "⛔ محتوای خشونت‌آمیز قابل ارسال نیست. پیام شما حذف شد.")
                                return True
            except:
                pass
    # ⭐⭐⭐ پایان چک محتوا ⭐⭐⭐

    # ⭐ چک بلاکی - اول لینکی، بعد کلی (فقط اگه همه لینک‌ها بلاک باشن)
    from database import is_user_blocked_from_link, get_user_anonymous_links
    if is_user_blocked_from_link(link_id, user_id):
        del reply_waiting[user_id]
        send(chat_id, "⛔ شما از این لینک بلاک شدید. پیام شما ارسال نشد.")
        return True
    # ⭐ بلاک کلی فقط وقتی اعمال بشه که همه لینک‌های فعال بلاک باشن
    if is_user_blocked(target_id, user_id):
        links = get_user_anonymous_links(target_id)
        active_links = [l for l in links if l['is_active']]
        all_blocked = all(is_user_blocked_from_link(l['id'], user_id) for l in active_links)
        if all_blocked:
            del reply_waiting[user_id]
            from database import get_user_display_name
            target_name = get_user_display_name(target_id) or f"کاربر {target_id}"
            send(chat_id, f"⛔ *{target_name}* شما را بلاک کرده است. پیام شما ارسال نشد.")
            return True

    del reply_waiting[user_id]

    # ⭐ گرفتن نام نمایشی فرستنده
    display_name = get_user_display_name(user_id)
    from helpers import get_user_name
    user_real_name = get_user_name(user_id) or f"کاربر {user_id}"
    sender_info = f"👤 از: *{display_name}*" if display_name else f"👤 از: {user_real_name}"

    # ⭐ چک کن لینک گروه داره یا نه
    from database import get_anonymous_link_group_info
    group_info = get_anonymous_link_group_info(link_id)
    link_group_id = group_info.get("group_id", 0)
    group_title = group_info.get("group_title", "")

    # ⭐ اگه گروه داره، target رو عوض کن
    actual_target = link_group_id if link_group_id and link_group_id != 0 else target_id
    is_group = link_group_id and link_group_id != 0

    # ⭐ اگه گروه داره، پیام رو به گروه بفرست (دقیقاً مثل پیوی)
    if is_group:
        # ⭐ اول پیام رو توی دیتابیس ذخیره کن تا msg_id داشته باشیم
        cur = db_conn.cursor()
        caption_text = text if text else ""
        media_type = "text"
        if msg:
            if msg.get("photo"): media_type = "PHOTO"
            elif msg.get("video"): media_type = "VIDEO"
            elif msg.get("animation"): media_type = "ANIMATION"
            elif msg.get("voice"): media_type = "VOICE"
            elif msg.get("sticker"): media_type = "STICKER"
            elif msg.get("document"): media_type = "DOCUMENT"

        sender_msg_id = msg.get("message_id", 0) if msg else 0

        cur.execute(
            "INSERT INTO anonymous_messages (from_user_id, message, chat_type, chat_id, link_id, sender_msg_id) VALUES (?, ?, 'group', ?, ?, ?)",
            (user_id, f"[{media_type}] {caption_text}" if media_type != "text" else caption_text, actual_target, link_id, sender_msg_id)
        )
        db_conn.commit()
        msg_id = cur.lastrowid

        # ⭐ گرفتن نام نمایشی فرستنده
        display_name = get_user_display_name(user_id)
        from helpers import get_user_name
        user_real_name = get_user_name(user_id) or f"کاربر {user_id}"
        sender_info = f"👤 از: *{display_name}*" if display_name else f"👤 از: {user_real_name}"

        # ⭐ دکمه‌های گیرنده در گروه (دقیقاً مثل پیوی)
        group_keyboard = {
            "inline_keyboard": [
                [
                    {"text": "👁️ خوندم", "callback_data": f"alink_seen_{msg_id}_{user_id}"},
                    {"text": "↩️ پاسخ", "callback_data": f"alink_reply_{msg_id}_{user_id}"}
                ],
                [
                    {"text": "⛔ مسدود", "callback_data": f"anon_open_panel_{msg_id}_{link_id}_{user_id}"},
                    {"text": "😊 ری‌اکشن", "callback_data": f"alink_react_{msg_id}_{user_id}"}
                ]
            ]
        }

        # ⭐ پیام ۱: اطلاعات فرستنده (مثل پیوی)
        api_call("sendMessage", json_data={
            "chat_id": actual_target,
            "text": f"👻 پیام ناشناس جدید!\n{sender_info}\n🔗 از طریق: *{link_name}* :"
        })

        # ⭐ پیام ۲: محتوای پیام + دکمه‌ها (دقیقاً مثل پیوی)
        result = send_any_media(
            actual_target,
            msg or {"text": text},
            caption_prefix="",
            reply_markup=group_keyboard
        )

        # ⭐⭐ ذخیره receiver_msg_id و target_chat_id برای ویرایش/حذف ⭐⭐
        if result and result.get("ok"):
            receiver_msg_id = result.get("result", {}).get("message_id", 0)
            if receiver_msg_id:
                cur.execute(
                    "UPDATE anonymous_messages SET sent_msg_id = ?, receiver_msg_id = ?, chat_id = ? WHERE id = ?",
                    (receiver_msg_id, receiver_msg_id, actual_target, msg_id)
                )
                db_conn.commit()
                info(f"✅ پیام #{msg_id} در گروه {actual_target} با receiver_msg_id {receiver_msg_id} ذخیره شد")
        else:
            info(f"⚠️ ارسال به گروه ناموفق: {result}")

        # ⭐ دکمه‌های فرستنده (ویرایش و حذف) - مثل پیوی
        sender_keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✏️ ویرایش", "callback_data": f"alink_edit_{msg_id}_{user_id}"},
                    {"text": "🗑️ حذف", "callback_data": f"anon_delete_self_{msg_id}_{user_id}"}
                ]
            ]
        }

        # ⭐ ریپلای روی پیام فرستنده
        api_call("sendMessage", json_data={
            "chat_id": chat_id,
            "text": f"✅ پیام ناشناس ارسال شد!",
            "reply_markup": sender_keyboard,
            "reply_to_message_id": sender_msg_id if sender_msg_id else None
        })

        # ⭐ حذف waiting state
        if user_id in reply_waiting:
            del reply_waiting[user_id]

        info(f"📨 پیام ناشناس جدید: {user_id} -> {actual_target} (گروه: {group_title})")
        return True

    # ⭐ ذخیره پیام در دیتابیس
    cur = db_conn.cursor()
    caption_text = text if text else ""
    media_type = "text"
    if msg:
        if msg.get("photo"): media_type = "PHOTO"
        elif msg.get("video"): media_type = "VIDEO"
        elif msg.get("animation"): media_type = "ANIMATION"
        elif msg.get("voice"): media_type = "VOICE"
        elif msg.get("sticker"): media_type = "STICKER"
        elif msg.get("document"): media_type = "DOCUMENT"

    # ⭐ ذخیره sender_msg_id
    sender_msg_id = msg.get("message_id", 0) if msg else 0

    cur.execute(
        "INSERT INTO anonymous_messages (from_user_id, message, chat_type, chat_id, link_id, sender_msg_id) VALUES (?, ?, 'private', ?, ?, ?)",
        (user_id, f"[{media_type}] {caption_text}" if media_type != "text" else caption_text, actual_target, link_id, sender_msg_id)
    )
    db_conn.commit()
    msg_id = cur.lastrowid

    # ⭐ چک کن این لینک کانال داره یا نه
    from database import get_anonymous_link_channel_info
    channel_info = get_anonymous_link_channel_info(link_id)
    has_channel = channel_info.get('channel_id', 0) != 0

    # ⭐ دکمه‌های گیرنده
    if has_channel:
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "👁️ خوندم", "callback_data": f"alink_seen_{msg_id}_{user_id}"},
                    {"text": "↩️ پاسخ", "callback_data": f"alink_reply_{msg_id}_{user_id}"}
                ],
                [
                    {"text": "📢 ارسال به کانال", "callback_data": f"alink_tochannel_{msg_id}_{user_id}"},
                ],
                [
                    {"text": "⛔ مسدود", "callback_data": f"anon_open_panel_{msg_id}_{link_id}_{user_id}"},
                    {"text": "😊 ری‌اکشن", "callback_data": f"alink_react_{msg_id}_{user_id}"}
                ]
            ]
        }
    else:
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "👁️ خوندم", "callback_data": f"alink_seen_{msg_id}_{user_id}"},
                    {"text": "↩️ پاسخ", "callback_data": f"alink_reply_{msg_id}_{user_id}"}
                ],
                [
                    {"text": "⛔ مسدود", "callback_data": f"anon_open_panel_{msg_id}_{link_id}_{user_id}"},
                    {"text": "😊 ری‌اکشن", "callback_data": f"alink_react_{msg_id}_{user_id}"}
                ]
            ]
        }

    actual_target = target_id

    # ⭐ اگه گیرنده صاحب لینک نیست، دکمه کانال رو حذف کن
    if has_channel and actual_target != target_id:
        # پیام به گروه میره، پس گیرنده صاحب لینک نیست
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "👁️ خوندم", "callback_data": f"alink_seen_{msg_id}_{user_id}"},
                    {"text": "↩️ پاسخ", "callback_data": f"alink_reply_{msg_id}_{user_id}"}
                ],
                [
                    {"text": "⛔ مسدود", "callback_data": f"anon_open_panel_{msg_id}_{link_id}_{user_id}"},
                    {"text": "😊 ری‌اکشن", "callback_data": f"alink_react_{msg_id}_{user_id}"}
                ]
            ]
        }

    # ⭐ پیام ۱: اطلاعات فرستنده
    if is_group:
        # پیام به گروه فرستاده میشه - فقط بگو از کیه
        header_text = f"👻 پیام ناشناس جدید!\n{sender_info}\n🔗 از طریق: *{link_name}* :"
    else:
        # پیام به پیوی فرستاده میشه - بگو از کدوم گروه و از کیه
        from database import get_anonymous_link_group_info
        group_info = get_anonymous_link_group_info(link_id)
        group_title = group_info.get("group_title", "")
        if group_title:
            header_text = f"👻 پیام ناشناس داری!\n{sender_info}\n👥 از گروه: *{group_title}*\n🔗 از طریق: *{link_name}* :"
        else:
            header_text = f"👻 پیام ناشناس داری!\n{sender_info}\n🔗 از طریق: *{link_name}* :"

    api_call("sendMessage", json_data={
        "chat_id": actual_target,
        "text": header_text
    })

    # ⭐ پیام ۲: محتوای پیام + دکمه‌ها
    result = send_any_media(
        actual_target,
        msg or {"text": text},
        caption_prefix="",
        reply_markup=keyboard
    )

    if result.get("ok"):
        receiver_msg_id = result.get("result", {}).get("message_id", 0)
        # ⭐ ذخیره receiver_msg_id و chat_id
        if receiver_msg_id:
            cur.execute(
                "UPDATE anonymous_messages SET sent_msg_id = ?, receiver_msg_id = ?, chat_id = ? WHERE id = ?",
                (receiver_msg_id, receiver_msg_id, actual_target, msg_id)
            )
            db_conn.commit()

    # ⭐ دکمه‌های فرستنده (ویرایش و حذف)
    sender_keyboard = {
        "inline_keyboard": [
            [
                {"text": "✏️ ویرایش", "callback_data": f"alink_edit_{msg_id}_{user_id}"},
                {"text": "🗑️ حذف", "callback_data": f"anon_delete_self_{msg_id}_{user_id}"}
            ]
        ]
    }

    # ⭐ ریپلای روی پیام فرستنده
    # ⭐ sender_msg_id قبلاً بالا تعریف شده

    api_call("sendMessage", json_data={
        "chat_id": chat_id,
        "text": f"✅ پیام ناشناس ارسال شد!",
        "reply_markup": sender_keyboard,
        "reply_to_message_id": sender_msg_id  # ⭐ ریپلای روی پیام اصلی
    })

    info(f"📨 پیام ناشناس جدید: {user_id} -> {actual_target} (لینک: {link_name}, گروه: {is_group})")
    return True


def _handle_old_link_reply(chat_id, user_id, text, msg, wait_info):
    """پردازش پیام از لینک قدیمی"""
    from state import reply_waiting
    from database import conn as db_conn, is_user_blocked

    if text in ["لغو", "انصراف", "/cancel", "cancel"]:
        del reply_waiting[user_id]
        send(chat_id, "❌ ارسال پیام ناشناس لغو شد.")
        return True

    target_id = wait_info["target"]
    link_id = wait_info.get("link_id", 0)

    # ⭐ چک بلاکی - اول چک کن برای این لینک خاص
    from database import is_user_blocked_from_link
    if link_id and is_user_blocked_from_link(link_id, user_id):
        del reply_waiting[user_id]
        send(chat_id, "⛔ شما از این لینک بلاک شدید. پیام شما ارسال نشد.")
        return True
    # اگه برای این لینک بلاک نبود، چک بلاکی کلی
    if is_user_blocked(target_id, user_id):
        del reply_waiting[user_id]
        from database import get_user_display_name
        target_name = get_user_display_name(target_id) or f"کاربر {target_id}"
        send(chat_id, f"⛔ *{target_name}* شما را بلاک کرده است. پیام شما ارسال نشد.")
        return True

    del reply_waiting[user_id]

    # ⭐ ذخیره پیام در دیتابیس
    cur = db_conn.cursor()
    caption_text = text if text else ""
    media_type = "text"
    if msg:
        if msg.get("photo"): media_type = "PHOTO"
        elif msg.get("video"): media_type = "VIDEO"
        elif msg.get("animation"): media_type = "ANIMATION"
        elif msg.get("voice"): media_type = "VOICE"
        elif msg.get("sticker"): media_type = "STICKER"
        elif msg.get("document"): media_type = "DOCUMENT"

    # ⭐ ذخیره sender_msg_id
    sender_msg_id = msg.get("message_id", 0) if msg else 0

    cur.execute(
        "INSERT INTO anonymous_messages (from_user_id, message, chat_type, chat_id, sender_msg_id) VALUES (?, ?, 'private', ?, ?)",
        (user_id, f"[{media_type}] {caption_text}" if media_type != "text" else caption_text, target_id, sender_msg_id)
    )
    db_conn.commit()
    msg_id = cur.lastrowid

    # ⭐ چک کن این لینک کانال داره یا نه
    from database import get_anonymous_link_channel_info
    channel_info = get_anonymous_link_channel_info(link_id)
    has_channel = channel_info.get('channel_id', 0) != 0

    # ⭐ دکمه‌های گیرنده
    if has_channel:
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "👁️ خوندم", "callback_data": f"alink_seen_{msg_id}_{user_id}"},
                    {"text": "↩️ پاسخ", "callback_data": f"alink_reply_{msg_id}_{user_id}"}
                ],
                [
                    {"text": "📢 ارسال به کانال", "callback_data": f"alink_tochannel_{msg_id}_{user_id}"},
                ],
                [
                    {"text": "⛔ مسدود", "callback_data": f"anon_open_panel_{msg_id}_{link_id}_{user_id}"},
                    {"text": "😊 ری‌اکشن", "callback_data": f"alink_react_{msg_id}_{user_id}"}
                ]
            ]
        }
    else:
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "👁️ خوندم", "callback_data": f"alink_seen_{msg_id}_{user_id}"},
                    {"text": "↩️ پاسخ", "callback_data": f"alink_reply_{msg_id}_{user_id}"}
                ],
                [
                    {"text": "⛔ مسدود", "callback_data": f"anon_open_panel_{msg_id}_{link_id}_{user_id}"},
                    {"text": "😊 ری‌اکشن", "callback_data": f"alink_react_{msg_id}_{user_id}"}
                ]
            ]
        }

    actual_target = target_id

    # ⭐ اگه گیرنده صاحب لینک نیست، دکمه کانال رو حذف کن
    if has_channel and actual_target != target_id:
        # پیام به گروه میره، پس گیرنده صاحب لینک نیست
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "👁️ خوندم", "callback_data": f"alink_seen_{msg_id}_{user_id}"},
                    {"text": "↩️ پاسخ", "callback_data": f"alink_reply_{msg_id}_{user_id}"}
                ],
                [
                    {"text": "⛔ مسدود", "callback_data": f"anon_open_panel_{msg_id}_{link_id}_{user_id}"},
                    {"text": "😊 ری‌اکشن", "callback_data": f"alink_react_{msg_id}_{user_id}"}
                ]
            ]
        }

    # ⭐ پیام ۱: اطلاعات فرستنده
    from helpers import get_user_name
    user_real_name = get_user_name(user_id) or f"کاربر {user_id}"
    api_call("sendMessage", json_data={
        "chat_id": target_id,
        "text": f"👻 پیام ناشناس داری! | 👤 {user_real_name} :"
    })

    # ⭐ پیام ۲: محتوای پیام + دکمه‌ها
    result = send_any_media(
        target_id,
        msg or {"text": text},
        caption_prefix="",
        reply_markup=keyboard
    )

    if result.get("ok") and result.get("result", {}).get("message_id"):
        receiver_msg_id = result["result"]["message_id"]
        cur.execute(
            "UPDATE anonymous_messages SET sent_msg_id = ?, receiver_msg_id = ?, chat_id = ? WHERE id = ?",
            (receiver_msg_id, receiver_msg_id, target_id, msg_id)
        )
        db_conn.commit()

    # ⭐ دکمه‌های فرستنده (ویرایش و حذف)
    sender_keyboard = {
        "inline_keyboard": [
            [
                {"text": "✏️ ویرایش", "callback_data": f"alink_edit_{msg_id}_{user_id}"},
                {"text": "🗑️ حذف", "callback_data": f"anon_delete_self_{msg_id}_{user_id}"}
            ]
        ]
    }

    api_call("sendMessage", json_data={
        "chat_id": chat_id,
        "text": f"✅ پیام ناشناس ارسال شد!",
        "reply_markup": sender_keyboard
    })

    return True


# ==================== دکمه‌های اینلاین ====================

def handle_anonymous_inline_callback(cdata, cid, uid, mid, chat_id):
    """پردازش دکمه‌های اینلاین پیام ناشناس"""

    # ⭐ خوندم
    if cdata.startswith("alink_seen_"):
        parts = cdata.replace("alink_seen_", "").split("_")
        msg_id = int(parts[0])
        sender_id = int(parts[1])

        from database import conn as db_conn
        cur = db_conn.cursor()
        cur.execute("SELECT sender_msg_id, receiver_msg_id, chat_id FROM anonymous_messages WHERE id = ?", (msg_id,))
        row = cur.fetchone()

        if row:
            sender_msg_id = row[0]  # message_id توی چت فرستنده
            receiver_msg_id = row[1]  # message_id توی چت گیرنده (گروه یا پیوی)
            target_chat_id = row[2]  # chat_id گیرنده (گروه یا پیوی)

            # ⭐ همیشه به فرستنده اصلی بگو (حتی اگه پیام توی گروه باشه)
            if sender_msg_id and sender_msg_id > 0:
                send(sender_id, "👁️ پیام ناشناس شما توسط گیرنده دیده شد!", reply_to=sender_msg_id)
            else:
                send(sender_id, "👁️ پیام ناشناس شما توسط گیرنده دیده شد!")

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ خوندم", "callback_data": "no_action"},
                    {"text": "↩️ پاسخ", "callback_data": f"alink_reply_{msg_id}_{sender_id}"}
                ],
                [
                    {"text": "⛔ مسدود", "callback_data": f"anon_open_panel_{msg_id}_{0}_{sender_id}"},
                    {"text": "😊 ری‌اکشن", "callback_data": f"alink_react_{msg_id}_{sender_id}"}
                ]
            ]
        }
        try:
            requests.post(f"{BASE_URL}editMessageReplyMarkup", json={
                "chat_id": chat_id, "message_id": mid, "reply_markup": keyboard
            }, timeout=5)
        except:
            pass

        try:
            requests.post(f"{BASE_URL}answerCallbackQuery", json={
                "callback_query_id": cid, "text": "👁️", "show_alert": False
            }, timeout=5)
        except:
            pass
        return True

    # ⭐ پاسخ ناشناس
    if cdata.startswith("alink_reply_"):
        parts = cdata.replace("alink_reply_", "").split("_")
        msg_id = int(parts[0])
        sender_id = int(parts[1])

        from state import reply_waiting

        # ⭐ چک کن پیام توی گروه هست یا نه
        from database import conn as db_conn
        cur = db_conn.cursor()
        cur.execute("SELECT chat_id, link_id FROM anonymous_messages WHERE id = ?", (msg_id,))
        row = cur.fetchone()
        original_chat_id = row[0] if row else sender_id
        original_link_id = row[1] if row and len(row) > 1 else 0

        # ⭐ اگه لینک داره و گروه داره، یعنی توی گروهه
        is_group_msg = False
        if original_link_id:
            from database import get_anonymous_link_group
            grp = get_anonymous_link_group(original_link_id)
            if grp and grp != 0:
                is_group_msg = True
                original_chat_id = grp  # آیدی گروه رو جایگزین کن

        reply_waiting[uid] = {
            "type": "alink_reply",
            "id": msg_id,
            "target": sender_id,
            "original_chat_id": original_chat_id,
            "is_group_msg": is_group_msg
        }

        # ⭐ گرفتن نام نمایشی فرستنده اصلی
        from database import get_user_display_name
        from helpers import get_user_name
        sender_display = get_user_display_name(sender_id) or get_user_name(sender_id) or f"کاربر {sender_id}"

        # ⭐ تنظیم reply_waiting
        from state import reply_waiting
        reply_waiting[uid] = {
            "type": "alink_reply",
            "id": msg_id,
            "target": sender_id,
            "original_chat_id": original_chat_id,
            "is_group_msg": is_group_msg
        }

        # ⭐ پیام توضیحی در چت (بدون دکمه لغو و بدون Alert)
        keyboard = {
            "inline_keyboard": [[{"text": "❌ لغو", "callback_data": "cancel_waiting"}]]
        }
        api_call("sendMessage", json_data={
            "chat_id": chat_id,
            "text": f"✏️ *پاسخ ناشناس*\n\n📎 شما در حال پاسخ به *{sender_display}* هستید\n✏️ پیامت رو بنویس:",
            "reply_markup": keyboard
        })
        return True

    # ⭐ ری‌اکشن - نمایش پنل ایموجی
    if cdata.startswith("alink_react_"):
        parts = cdata.replace("alink_react_", "").split("_")
        msg_id = int(parts[0])
        sender_id = int(parts[1])

        # ⭐ پنل انتخاب ری‌اکشن
        react_keyboard = {
            "inline_keyboard": [
                [{"text": "📝 ری‌اکشن را انتخاب کنید", "callback_data": "no_action"}],
                [
                    {"text": "😊", "callback_data": f"alink_remoji_{msg_id}_{sender_id}_😊"},
                    {"text": "😂", "callback_data": f"alink_remoji_{msg_id}_{sender_id}_😂"},
                    {"text": "❤️", "callback_data": f"alink_remoji_{msg_id}_{sender_id}_❤️"}
                ],
                [
                    {"text": "👍", "callback_data": f"alink_remoji_{msg_id}_{sender_id}_👍"},
                    {"text": "👎", "callback_data": f"alink_remoji_{msg_id}_{sender_id}_👎"},
                    {"text": "😢", "callback_data": f"alink_remoji_{msg_id}_{sender_id}_😢"}
                ],
                [
                    {"text": "😡", "callback_data": f"alink_remoji_{msg_id}_{sender_id}_😡"},
                    {"text": "🤔", "callback_data": f"alink_remoji_{msg_id}_{sender_id}_🤔"},
                    {"text": "👏", "callback_data": f"alink_remoji_{msg_id}_{sender_id}_👏"}
                ],
                [{"text": "🔙 بازگشت", "callback_data": f"alink_rback_{msg_id}_{sender_id}"}]
            ]
        }

        try:
            requests.post(f"{BASE_URL}editMessageReplyMarkup", json={
                "chat_id": chat_id, "message_id": mid, "reply_markup": react_keyboard
            }, timeout=5)
        except:
            pass

        try:
            requests.post(f"{BASE_URL}answerCallbackQuery", json={
                "callback_query_id": cid, "text": "😊 ری‌اکشن مورد نظر رو انتخاب کن", "show_alert": False
            }, timeout=5)
        except:
            pass
        return True

    # ⭐ ارسال ری‌اکشن
    if cdata.startswith("alink_remoji_"):
        parts = cdata.split("_")
        # فرمت: alink_remoji_msgid_senderid_emoji
        msg_id = int(parts[2])
        sender_id = int(parts[3])
        emoji = parts[4] if len(parts) > 4 else "😊"

        # ⭐ گرفتن نام نمایشی ری‌اکشن‌دهنده
        from database import get_user_display_name
        display_name = get_user_display_name(uid)
        from helpers import get_user_name
        reactor_name = display_name if display_name else (get_user_name(uid) or f"کاربر {uid}")

        # ⭐ گرفتن اطلاعات پیام
        from database import conn as db_conn
        cur = db_conn.cursor()
        cur.execute("SELECT sender_msg_id, receiver_msg_id, chat_id FROM anonymous_messages WHERE id = ?", (msg_id,))
        row = cur.fetchone()

        if row:
            sender_msg_id = row[0]
            receiver_msg_id = row[1]
            target_chat_id = row[2]

            # ⭐ همیشه به فرستنده اصلی بگو (حتی اگه پیام توی گروه باشه)
            if sender_msg_id and sender_msg_id > 0:
                send(sender_id, f"👤 کاربر {reactor_name} ری‌اکشن {emoji} را به پیام شما ارسال کرد", reply_to=sender_msg_id)
            else:
                send(sender_id, f"👤 کاربر {reactor_name} ری‌اکشن {emoji} را به پیام شما ارسال کرد")
        else:
            send(sender_id, f"👤 کاربر {reactor_name} ری‌اکشن {emoji} را به پیام شما ارسال کرد")

        # ⭐ برگشت به دکمه‌های اصلی
        back_keyboard = {
            "inline_keyboard": [
                [
                    {"text": "👁️ خوندم", "callback_data": f"alink_seen_{msg_id}_{sender_id}"},
                    {"text": "↩️ پاسخ", "callback_data": f"alink_reply_{msg_id}_{sender_id}"}
                ],
                [
                    {"text": "⛔ مسدود", "callback_data": f"anon_open_panel_{msg_id}_{0}_{sender_id}"},
                    {"text": "😊 ری‌اکشن", "callback_data": f"alink_react_{msg_id}_{sender_id}"}
                ]
            ]
        }

        try:
            requests.post(f"{BASE_URL}editMessageReplyMarkup", json={
                "chat_id": chat_id, "message_id": mid, "reply_markup": back_keyboard
            }, timeout=5)
        except:
            pass

        try:
            requests.post(f"{BASE_URL}answerCallbackQuery", json={
                "callback_query_id": cid, "text": f"{emoji} ری‌اکشن ارسال شد!", "show_alert": False
            }, timeout=5)
        except:
            pass
        return True

    # ⭐ بازگشت از پنل ری‌اکشن
    if cdata.startswith("alink_rback_"):
        parts = cdata.replace("alink_rback_", "").split("_")
        msg_id = int(parts[0])
        sender_id = int(parts[1])

        # ⭐ برگشت به دکمه‌های اصلی
        back_keyboard = {
            "inline_keyboard": [
                [
                    {"text": "👁️ خوندم", "callback_data": f"alink_seen_{msg_id}_{sender_id}"},
                    {"text": "↩️ پاسخ", "callback_data": f"alink_reply_{msg_id}_{sender_id}"}
                ],
                [
                    {"text": "⛔ مسدود", "callback_data": f"anon_open_panel_{msg_id}_{0}_{sender_id}"},
                    {"text": "😊 ری‌اکشن", "callback_data": f"alink_react_{msg_id}_{sender_id}"}
                ]
            ]
        }

        try:
            requests.post(f"{BASE_URL}editMessageReplyMarkup", json={
                "chat_id": chat_id, "message_id": mid, "reply_markup": back_keyboard
            }, timeout=5)
        except:
            pass

        try:
            requests.post(f"{BASE_URL}answerCallbackQuery", json={
                "callback_query_id": cid, "text": "🔙 بازگشت", "show_alert": False
            }, timeout=5)
        except:
            pass
        return True

    # ⭐ ارسال پیام به کانال
    if cdata.startswith("alink_tochannel_"):
        parts = cdata.replace("alink_tochannel_", "").split("_")
        msg_id = int(parts[0])
        sender_id = int(parts[1])

        # ⭐ فقط صاحب لینک می‌تونه ارسال به کانال کنه
        from database import conn as db_conn
        cur = db_conn.cursor()
        cur.execute("SELECT link_id FROM anonymous_messages WHERE id = ?", (msg_id,))
        link_row = cur.fetchone()
        if link_row and link_row[0]:
            cur.execute("SELECT owner_id FROM anonymous_links WHERE id = ?", (link_row[0],))
            owner_row = cur.fetchone()
            if owner_row and owner_row[0] != uid:
                try:
                    requests.post(f"{BASE_URL}answerCallbackQuery", json={
                        "callback_query_id": cid, "text": "⛔ فقط صاحب لینک می‌تونه ارسال کنه!", "show_alert": True
                    }, timeout=5)
                except: pass
                return True

        cur.execute("SELECT message, from_user_id, link_id FROM anonymous_messages WHERE id = ?", (msg_id,))
        row = cur.fetchone()

        if row:
            msg_text, from_user_id, link_id = row

            from database import get_anonymous_link_channel_info, get_user_anonymous_links
            channel_info = get_anonymous_link_channel_info(link_id)
            channel_id = channel_info.get('channel_id', 0)

            if not channel_id:
                try:
                    requests.post(f"{BASE_URL}answerCallbackQuery", json={
                        "callback_query_id": cid, "text": "❌ این لینک کانال نداره!", "show_alert": True
                    }, timeout=5)
                except: pass
                return True

            links = get_user_anonymous_links(uid)
            link_name = "ناشناس"
            for link in links:
                if link['id'] == link_id:
                    link_name = link['link_name']
                    break

            bot_username = _get_bot_username()
            anon_link = f"https://ble.ir/{bot_username}?start=anon_{link_id}"

            from database import get_user_display_name
            display_name = get_user_display_name(from_user_id)
            from helpers import get_user_name
            sender_name = display_name if display_name else (get_user_name(from_user_id) or f"کاربر {from_user_id}")

            channel_text = f"[پیام ناشناس :]({anon_link})\n{msg_text[:2000]}"

            channel_keyboard = {
                "inline_keyboard": [
                    [{"text": "✏️ ارسال پیام ناشناس", "url": anon_link}]
                ]
            }

            result = requests.post(f"{BASE_URL}sendMessage", json={
                "chat_id": channel_id,
                "text": channel_text,
                "reply_markup": channel_keyboard
            }, timeout=5)

            if result.json().get("ok"):
                try:
                    requests.post(f"{BASE_URL}answerCallbackQuery", json={
                        "callback_query_id": cid, "text": "✅ پیام به کانال ارسال شد!", "show_alert": True
                    }, timeout=5)
                except: pass
            else:
                try:
                    requests.post(f"{BASE_URL}answerCallbackQuery", json={
                        "callback_query_id": cid, "text": "❌ ارسال نشد!", "show_alert": True
                    }, timeout=5)
                except: pass
        return True

    # ⭐ ویرایش پیام (فقط فرستنده)
    if cdata.startswith("alink_edit_"):
        parts = cdata.replace("alink_edit_", "").split("_")
        msg_id = int(parts[0])
        sender_id = int(parts[1])

        # ⭐ چک کن فقط فرستنده میتونه ویرایش کنه
        if uid != sender_id:
            try:
                requests.post(f"{BASE_URL}answerCallbackQuery", json={
                    "callback_query_id": cid,
                    "text": "⛔ فقط فرستنده میتونه پیام رو ویرایش کنه!",
                    "show_alert": True
                }, timeout=5)
            except:
                pass
            return True

        # ⭐ تنظیم reply_waiting برای ویرایش
        from state import reply_waiting
        reply_waiting[uid] = {
            "type": "alink_edit",
            "msg_id": msg_id,
            "target": uid  # خود فرستنده
        }

        # ⭐ پیام توضیحی در چت (بدون Alert)
        keyboard = {
            "inline_keyboard": [[{"text": "❌ لغو", "callback_data": "cancel_waiting"}]]
        }
        api_call("sendMessage", json_data={
            "chat_id": chat_id,
            "text": "✏️ *ویرایش پیام ناشناس*\n\nپیام جدید رو بفرست:",
            "reply_markup": keyboard
        })
        return True

    return False

def handle_anonymous_delete(callback_data, callback_id, user_id, message_id, chat_id):
    """حذف پیام ناشناس توسط فرستنده (ظرف 48 ساعت)"""
    import time
    from database import conn as db_conn
    from logger import info, error_log

    parts = callback_data.split("_")
    if len(parts) < 4:
        error_log("anonymous_delete", "تعداد بخش‌ها کم است")
        return False

    if parts[2] == "self":
        msg_id = int(parts[3])
        sender_id = int(parts[4])
    else:
        msg_id = int(parts[2])
        sender_id = int(parts[3])

    if user_id != sender_id:
        answer_callback(callback_id, "⛔ شما اجازه حذف این پیام را ندارید!", True)
        return True

    cur = db_conn.cursor()
    cur.execute("SELECT created_at, receiver_msg_id, chat_id, message FROM anonymous_messages WHERE id = ?", (msg_id,))
    row = cur.fetchone()

    if not row:
        answer_callback(callback_id, "❌ پیام پیدا نشد!", True)
        return True

    created_at_str = row[0]
    receiver_msg_id = row[1]
    target_chat_id = row[2]
    msg_text = row[3]

    # ⭐⭐ اگر target_chat_id یا receiver_msg_id خالی است، از دیتابیس اصلی استفاده کن
    if not target_chat_id or target_chat_id == 0 or not receiver_msg_id or receiver_msg_id == 0:
        # سعی کن از جدول anonymous_messages دوباره بگیر
        cur.execute("SELECT chat_id, receiver_msg_id FROM anonymous_messages WHERE id = ?", (msg_id,))
        row2 = cur.fetchone()
        if row2:
            target_chat_id = row2[0] or target_chat_id
            receiver_msg_id = row2[1] or receiver_msg_id

    # ⭐⭐ اگر باز هم receiver_msg_id صفر است، از sent_msg_id استفاده کن (برای پیام‌های پیوی)
    if not receiver_msg_id or receiver_msg_id == 0:
        # سعی کن sent_msg_id رو بگیر (message_id توی چت فرستنده)
        cur.execute("SELECT sent_msg_id, chat_id FROM anonymous_messages WHERE id = ?", (msg_id,))
        row3 = cur.fetchone()
        if row3 and row3[0]:
            receiver_msg_id = row3[0]
            # اگر target_chat_id هنوز خالی است، از chat_id کاربر (فرستنده) استفاده کن
            if not target_chat_id or target_chat_id == 0:
                target_chat_id = sender_id
        else:
            # آخرین راه: از chat_id که در دیتابیس ذخیره شده استفاده کن
            cur.execute("SELECT chat_id FROM anonymous_messages WHERE id = ?", (msg_id,))
            row4 = cur.fetchone()
            if row4 and row4[0]:
                target_chat_id = row4[0]

    try:
        created_time = time.mktime(time.strptime(created_at_str, "%Y-%m-%d %H:%M:%S"))
    except:
        from datetime import datetime
        dt = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
        created_time = dt.timestamp()

    hours_passed = (time.time() - created_time) / 3600

    if hours_passed > 48:
        answer_callback(callback_id, "⏰ زمان ۴۸ ساعته برای حذف پیام به پایان رسیده!", True)
        return True

    # حذف پیام از دیتابیس
    cur.execute("DELETE FROM anonymous_messages WHERE id = ?", (msg_id,))
    db_conn.commit()

    # ⭐ به جای حذف، پیام رو ویرایش کن و بنویس _حذف شده_
    if receiver_msg_id and target_chat_id:
        try:
            # ویرایش پیام به _حذف شده_
            edit_result = requests.post(f"{BASE_URL}editMessageText", json={
                "chat_id": target_chat_id,
                "message_id": receiver_msg_id,
                "text": "_حذف شده_",
                "parse_mode": "Markdown"
            }, timeout=5)

            if edit_result.json().get("ok"):
                answer_callback(callback_id, "🗑️ پیام ناشناس شما با موفقیت حذف شد!", True)
            else:
                # اگر ویرایش نشد، سعی کن حذف کنی
                result = delete_message(target_chat_id, receiver_msg_id)
                if result:
                    answer_callback(callback_id, "🗑️ پیام ناشناس شما با موفقیت حذف شد!", True)
                else:
                    answer_callback(callback_id, "⚠️ پیام حذف شد، اما حذف از چت گیرنده ناموفق بود!", True)
        except:
            # اگر خطا رخ داد، سعی کن حذف کنی
            result = delete_message(target_chat_id, receiver_msg_id)
            if result:
                answer_callback(callback_id, "🗑️ پیام ناشناس شما با موفقیت حذف شد!", True)
            else:
                answer_callback(callback_id, "⚠️ پیام حذف شد، اما حذف از چت گیرنده ناموفق بود!", True)
    else:
        answer_callback(callback_id, "⚠️ پیام حذف شد، اما پیام قبلاً از چت گیرنده پاک شده بود!", True)

    # ادیت پیام تأیید
    keyboard = {"inline_keyboard": [[{"text": "✅ حذف شد", "callback_data": "no_action"}]]}
    try:
        requests.post(f"{BASE_URL}editMessageReplyMarkup", json={
            "chat_id": chat_id, "message_id": message_id, "reply_markup": keyboard
        }, timeout=5)
    except:
        pass

    return True

# ==================== توابع پنل مدیریت پیام ناشناس ====================
def get_anon_message_and_buttons(msg_id, link_id, blocked_user_id, uid, is_panel_open=False):
    """دریافت پیام و ساخت دکمه‌های مربوطه"""
    from database import conn as db_conn
    from helpers import get_user_name, get_user_link
    from database import get_user_display_name
    from database import get_anonymous_link_channel_info

    cur = db_conn.cursor()

    # دریافت پیام از دیتابیس
    cur.execute("""
        SELECT id, message, from_user_id, link_id, created_at
        FROM anonymous_messages
        WHERE id = ?
    """, (msg_id,))
    row = cur.fetchone()

    if not row:
        return None, None

    msg_id_db = row[0]
    message_text = row[1]
    from_user_id = row[2]
    link_id_db = row[3]
    created_at = row[4]

    # دریافت اطلاعات لینک
    cur.execute("""
        SELECT id, link_name, owner_id, token
        FROM anonymous_links
        WHERE id = ?
    """, (link_id_db,))
    link_row = cur.fetchone()

    if not link_row:
        return None, None

    link_name = link_row[1]
    owner_id = link_row[2]

    # دریافت نام نمایشی از تابع database
    display_name = get_user_display_name(from_user_id) or f"کاربر {from_user_id}"

    # ساخت متن پیام
    if is_panel_open:
        # حالت پنل باز - متن پنل
        text = f"📢 *پنل مدیریت پیام ناشناس*\n\n"
        text += f"👤 از: *{display_name}*\n"
        text += f"📎 لینک: *{link_name}*\n"
        text += f"📝 متن: {message_text}\n\n"
        text += "👇 یکی از گزینه‌ها را انتخاب کن:"

        # دکمه‌های پنل (4 دکمه)
        buttons = [
            [{"text": "📢 گزارش", "callback_data": f"anon_report_{msg_id_db}_{link_id_db}_{from_user_id}"}],
            [{"text": "🚫 بن از چت ناشناس", "callback_data": f"anon_block_chat_{msg_id_db}_{link_id_db}_{from_user_id}"}],
            [{"text": "🚷 بن از کانال", "callback_data": f"anon_block_channel_{msg_id_db}_{link_id_db}_{from_user_id}"}],
            [{"text": "🔙 بازگشت", "callback_data": f"anon_back_{msg_id_db}_{link_id_db}_{from_user_id}"}]
        ]
    else:
        # حالت عادی - متن اصلی پیام
        text = f"👻 *پیام ناشناس*\n\n"
        text += f"📎 از لینک: *{link_name}*\n"
        text += f"📝 {message_text}"

        # ⭐⭐ چک کن این لینک کانال داره یا نه ⭐⭐
        channel_info = get_anonymous_link_channel_info(link_id_db)
        has_channel = channel_info.get('channel_id', 0) != 0

        # دکمه‌های اصلی کامل
        if uid == owner_id:
            # صاحب لینک
            if has_channel:
                # با دکمه ارسال به کانال
                buttons = [
                    [
                        {"text": "👁️ خوندم", "callback_data": f"alink_seen_{msg_id_db}_{from_user_id}"},
                        {"text": "↩️ پاسخ", "callback_data": f"alink_reply_{msg_id_db}_{from_user_id}"}
                    ],
                    [
                        {"text": "📢 ارسال به کانال", "callback_data": f"alink_tochannel_{msg_id_db}_{from_user_id}"}
                    ],
                    [
                        {"text": "🗑️ حذف", "callback_data": f"anon_delete_{msg_id_db}"},
                        {"text": "😊 ری‌اکشن", "callback_data": f"alink_react_{msg_id_db}_{from_user_id}"}
                    ]
                ]
            else:
                # بدون دکمه ارسال به کانال
                buttons = [
                    [
                        {"text": "👁️ خوندم", "callback_data": f"alink_seen_{msg_id_db}_{from_user_id}"},
                        {"text": "↩️ پاسخ", "callback_data": f"alink_reply_{msg_id_db}_{from_user_id}"}
                    ],
                    [
                        {"text": "🗑️ حذف", "callback_data": f"anon_delete_{msg_id_db}"},
                        {"text": "😊 ری‌اکشن", "callback_data": f"alink_react_{msg_id_db}_{from_user_id}"}
                    ]
                ]
        else:
            # کاربر عادی - بدون دکمه ارسال به کانال
            buttons = [
                [
                    {"text": "👁️ خوندم", "callback_data": f"alink_seen_{msg_id_db}_{from_user_id}"},
                    {"text": "↩️ پاسخ", "callback_data": f"alink_reply_{msg_id_db}_{from_user_id}"}
                ],
                [
                    {"text": "⛔ مسدود", "callback_data": f"anon_open_panel_{msg_id_db}_{link_id_db}_{from_user_id}"},
                    {"text": "😊 ری‌اکشن", "callback_data": f"alink_react_{msg_id_db}_{from_user_id}"}
                ]
            ]

    return text, buttons

def get_hot_question_and_buttons(q_id, link_id, from_user_id, uid, is_panel_open=False):
    """دریافت سوال صندلی داغ و ساخت دکمه‌های مربوطه"""
    from database import conn as db_conn, has_user_actioned
    from helpers import edit_inline_menu

    # ⭐ تبدیل link_id به int برای امنیت
    try:
        link_id = int(link_id)
    except:
        link_id = 0

    cur = db_conn.cursor()
    cur.execute("SELECT question_text, from_user_id FROM hot_seat_questions WHERE id = ?", (q_id,))
    row = cur.fetchone()
    if not row:
        return None, None

    question_text = row[0]
    from_user_id = row[1] or 0

    # چک کن کاربر قبلاً کدوم دکمه‌ها رو زده
    reported = has_user_actioned(q_id, uid, "report")
    blocked_chat = has_user_actioned(q_id, uid, "block_chat")
    blocked_channel = has_user_actioned(q_id, uid, "block_channel")

    if is_panel_open:
        report_text = "📢 گزارش ✅" if reported else "📢 گزارش"
        block_chat_text = "🚫 بن از چت ✅" if blocked_chat else "🚫 بن از چت"

        buttons = [
            [{"text": report_text, "callback_data": f"hot_report_{q_id}_{link_id}_{from_user_id}"}],
            [{"text": block_chat_text, "callback_data": f"hot_block_chat_{q_id}_{link_id}_{from_user_id}"}]
        ]

        # دکمه بن از کانال (فقط اگه کانال تنظیم شده باشه)
        from helpers import get_link_channel_id
        channel_id = get_link_channel_id(link_id)
        if channel_id and channel_id != 0:
            block_channel_text = "🚷 بن از کانال ✅" if blocked_channel else "🚷 بن از کانال"
            buttons.append([{"text": block_channel_text, "callback_data": f"hot_block_channel_{q_id}_{link_id}_{from_user_id}"}])

        buttons.append([{"text": "🔙 بازگشت", "callback_data": f"hot_back_{q_id}_{link_id}_{from_user_id}"}])

        return question_text, buttons
    else:
        buttons = [[{"text": "⛔ مسدود", "callback_data": f"hot_open_panel_{q_id}_{link_id}_{from_user_id}"}]]
        return question_text, buttons

# ==================== پاسخ به ناشناس ====================

def handle_anonymous_reply_message(chat_id, user_id, text, msg=None):
    """پردازش پاسخ به پیام ناشناس"""
    from state import reply_waiting
    from helpers import send_any_media

    if user_id not in reply_waiting:
        return False

    wait_info = reply_waiting[user_id]

    if wait_info.get("type") != "alink_reply":
        return False

    if text in ["لغو", "انصراف", "cancel"]:
        del reply_waiting[user_id]
        send(chat_id, "❌ پاسخ ناشناس لغو شد.")
        return True

    # ⭐ چک فحش (فقط لیست)
    if text:
        import os
        badwords_file = os.path.join(os.path.dirname(__file__), "..", "data", "badwords.txt")
        is_bad = False
        try:
            with open(badwords_file, "r", encoding="utf-8") as f:
                badwords_list = [line.strip().lower() for line in f if line.strip()]

            text_lower = text.lower()
            for badword in badwords_list:
                if badword in text_lower:
                    is_bad = True
                    break
        except:
            pass

        if is_bad:
            del reply_waiting[user_id]
            send(chat_id, "⛔ پاسخ شما حاوی کلمات نامناسب است و ارسال نشد.")
            return True

    # ⭐ چک NSFW و Gore برای پاسخ ناشناس
    if msg and (msg.get("photo") or msg.get("video") or msg.get("animation")):
        try:
            import os as _os
            import time as _time
            file_id = None
            if msg.get("photo"):
                file_id = msg["photo"][-1]["file_id"]
            elif msg.get("video"):
                file_id = msg["video"]["file_id"]
            elif msg.get("animation"):
                file_id = msg["animation"]["file_id"]

            if file_id:
                file_info = requests.get(f"{BASE_URL}getFile?file_id={file_id}").json()
                file_path = file_info.get("result", {}).get("file_path", "")
                if file_path:
                    download_url = f"https://tapi.bale.ai/file/bot262177859:Yln_PupSbSxRmopfmgYhUI1c1VaNWt2CmLU/{file_path}"
                    temp_dir = _os.path.join(_os.path.dirname(__file__), "..", "temp")
                    _os.makedirs(temp_dir, exist_ok=True)
                    ext = ".mp4" if msg.get("video") or msg.get("animation") else ".jpg"
                    local_path = _os.path.join(temp_dir, f"reply_nsfw_{user_id}_{_time.time()}{ext}")
                    r = requests.get(download_url, timeout=30)
                    with open(local_path, 'wb') as f:
                        f.write(r.content)

                    # چک NSFW
                    try:
                        from dataset.nsfw_detector import check_nsfw_from_path
                        nsfw_score = check_nsfw_from_path(local_path)
                        if nsfw_score > 0.7:
                            _os.remove(local_path)
                            del reply_waiting[user_id]
                            send(chat_id, "⛔ محتوای نامناسب (+18) قابل ارسال نیست.")
                            return True
                    except:
                        pass

                    # چک Gore
                    try:
                        from dataset.gore_vit_detector import check_gore_score_from_path
                        gore_score = check_gore_score_from_path(local_path)
                        if gore_score > 0.4:
                            _os.remove(local_path)
                            del reply_waiting[user_id]
                            send(chat_id, "⛔ محتوای خشونت‌آمیز قابل ارسال نیست.")
                            return True
                    except:
                        pass

                    try:
                        _os.remove(local_path)
                    except:
                        pass
        except:
            pass


    target_id = wait_info["target"]

    # ⭐ چک بلاکی
    from database import is_user_blocked
    if is_user_blocked(target_id, user_id):
        del reply_waiting[user_id]
        from database import get_user_display_name
        target_name = get_user_display_name(target_id) or f"کاربر {target_id}"
        send(chat_id, f"⛔ *{target_name}* شما را بلاک کرده است. پیام شما ارسال نشد.")
        return True

    reply_msg_id = wait_info.get("id", 0)

    # ⭐ اینارو قبل از پاک کردن بگیر
    is_group_reply = wait_info.get("is_group_msg", False)
    original_chat_id = wait_info.get("original_chat_id", target_id)

    del reply_waiting[user_id]

    # ⭐ گرفتن اسم نمایشی پاسخ‌دهنده
    from database import get_user_display_name
    display_name = get_user_display_name(user_id)
    from helpers import get_user_name
    user_real_name = get_user_name(user_id) or f"کاربر {user_id}"
    sender_name = display_name if display_name else user_real_name

    # ⭐ اگه پاسخ از گروه میاد، اسم کاربر رو هم اضافه کن
    if msg and msg.get("chat", {}).get("type") == "group":
        from helpers import get_user_name
        user_name = msg.get("from", {}).get("first_name", "")
        sender_name = f"{user_name} (از گروه)"

    # ⭐ ذخیره پیام با sender_msg_id
    from database import conn as db_conn
    cur = db_conn.cursor()
    sender_msg_id = msg.get("message_id", 0) if msg else 0
    cur.execute(
        "INSERT INTO anonymous_messages (from_user_id, message, chat_type, chat_id, sender_msg_id) VALUES (?, ?, 'private', ?, ?)",
        (user_id, text or "[MEDIA]", target_id, sender_msg_id)
    )
    db_conn.commit()
    new_msg_id = cur.lastrowid

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "👁️ خوندم", "callback_data": f"alink_seen_{new_msg_id}_{user_id}"},
                {"text": "↩️ پاسخ", "callback_data": f"alink_reply_{new_msg_id}_{user_id}"}
            ],
            [
                {"text": "⛔ مسدود", "callback_data": f"anon_open_panel_{new_msg_id}_{0}_{user_id}"},
                {"text": "😊 ری‌اکشن", "callback_data": f"alink_react_{new_msg_id}_{user_id}"}
            ]
        ]
    }

    # ⭐ گرفتن نام نمایشی پاسخ‌دهنده
    sender_info = f"👤 از: *{sender_name}*"

    # ⭐ اگه پاسخ‌دهنده توی گروهه، پاسخ رو بفرست به پیوی فرستنده
    # اگه پاسخ‌دهنده توی پیویه (صاحب لینک)، پاسخ رو بفرست به گروه
    if msg and msg.get("chat", {}).get("type") == "group":
        # پاسخ از گروه → بفرست به پیوی فرستنده
        reply_target = target_id
        reply_prefix = "گروه"
    elif is_group_reply and original_chat_id and original_chat_id != target_id:
        # پیام اصلی توی گروه بود، و پاسخ‌دهنده صاحب لینک (در پیوی) است → بفرست به گروه
        reply_target = original_chat_id
        reply_prefix = "گروه"
    elif is_group_reply and original_chat_id == target_id:
        # پاسخ‌دهنده توی پیوی صاحب لینکه (پیام اصلی هم توی پیوی بود)
        reply_target = target_id
        reply_prefix = "پیوی"
    else:
        reply_target = target_id
        reply_prefix = "پیوی"

    # ⭐ پیام ۱: اطلاعات با نام نمایشی
    api_call("sendMessage", json_data={
        "chat_id": reply_target,
        "text": f"👻 پاسخ ناشناس از {reply_prefix}!\n{sender_info} :"
    })

    # ⭐ پیام ۲: محتوا
    result = send_any_media(
        reply_target,
        msg or {"text": text},
        caption_prefix="",
        reply_markup=keyboard
    )

    if result and result.get("ok"):
        # ⭐ ذخیره receiver_msg_id برای پاسخ
        receiver_msg_id = result.get("result", {}).get("message_id", 0)
        if receiver_msg_id:
            # ⭐ chat_id رو بر اساس جایی که پیام واقعاً ارسال شده ذخیره کن
            # پیام به reply_target ارسال شده (که میتونه پیوی یا گروه باشه)
            cur.execute(
                "UPDATE anonymous_messages SET sent_msg_id = ?, receiver_msg_id = ?, chat_id = ? WHERE id = ?",
                (receiver_msg_id, receiver_msg_id, reply_target, new_msg_id)
            )
            db_conn.commit()
            info(f"✅ پاسخ #{new_msg_id} با receiver_msg_id {receiver_msg_id} در chat_id {reply_target} ذخیره شد")

        # ⭐ دکمه‌های ویرایش و حذف برای پاسخ هم باشه
        reply_keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✏️ ویرایش", "callback_data": f"alink_edit_{new_msg_id}_{user_id}"},
                    {"text": "🗑️ حذف", "callback_data": f"anon_delete_self_{new_msg_id}_{user_id}"}
                ]
            ]
        }
        # ⭐ ریپلای روی پیام پاسخ‌دهنده با دکمه‌ها
        api_call("sendMessage", json_data={
            "chat_id": chat_id,
            "text": f"✅ پاسخ ناشناس ارسال شد!",
            "reply_markup": reply_keyboard,
            "reply_to_message_id": sender_msg_id if sender_msg_id else None
        })
    else:
        from logger import error_log
        error_log("anonymous_reply_failed", f"target={target_id}, user={user_id}, result={result}")
        send(chat_id, "❌ ارسال نشد.\n⚠️ کاربر مورد نظر ربات رو استارت نکرده یا بلاک کرده است.")

    return True

def show_copy_links_panel(chat_id, user_id, message_id=None):
    """نمایش پنل کپی لینک‌ها با دکمه‌های copy_text"""
    from database import get_user_anonymous_links

    links = get_user_anonymous_links(user_id)
    active_links = [link for link in links if link['is_active']]

    if not active_links:
        text = "❌ هیچ لینک فعالی نداری!"
        keyboard = [[{"text": "🔙 بازگشت", "callback_data": "anol_back"}]]
    else:
        text = "📋 *لینک‌های فعال برای کپی:*\n\n"
        text += "👇 روی هر لینک کلیک کن تا کپی بشه:\n"

        keyboard = []
        for link in active_links:
            bot_username = _get_bot_username()
            link_url = f"https://ble.ir/{bot_username}?start=anon_{link['token']}"

            # ⭐ دکمه با copy_text
            keyboard.append([
                {
                    "text": f"📋 {link['link_name']}",
                    "copy_text": {"text": link_url}
                }
            ])

        keyboard.append([{"text": "🔙 بازگشت", "callback_data": "anol_back"}])

    if message_id:
        try:
            requests.post(f"{BASE_URL}editMessageText", json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "reply_markup": {"inline_keyboard": keyboard},
                "parse_mode": "Markdown"
            }, timeout=5)
        except:
            api_call("sendMessage", json_data={
                "chat_id": chat_id,
                "text": text,
                "reply_markup": {"inline_keyboard": keyboard}
            })
    else:
        api_call("sendMessage", json_data={
            "chat_id": chat_id,
            "text": text,
            "reply_markup": {"inline_keyboard": keyboard}
        })

def show_link_security_panel(chat_id, user_id, link_id, message_id=None):
    """نمایش پنل تنظیمات امنیتی پیشرفته برای یه لینک خاص"""
    from database import get_anonymous_link_security, get_user_anonymous_links, conn as db_conn
    from helpers import edit_inline_menu, send_inline_keyboard

    # پیدا کردن اسم لینک
    links = get_user_anonymous_links(user_id)
    link_name = "ناشناس"
    for link in links:
        if link['id'] == link_id:
            link_name = link['link_name']
            break

    # گرفتن تنظیمات از دیتابیس
    cur = db_conn.cursor()

    # چک کردن وجود ستون‌های جدید (migration)
    try:
        cur.execute("SELECT anti_media FROM anonymous_links LIMIT 1")
    except:
        cur.execute("ALTER TABLE anonymous_links ADD COLUMN anti_media INTEGER DEFAULT 0")
        cur.execute("ALTER TABLE anonymous_links ADD COLUMN anti_photo INTEGER DEFAULT 0")
        cur.execute("ALTER TABLE anonymous_links ADD COLUMN anti_video INTEGER DEFAULT 0")
        cur.execute("ALTER TABLE anonymous_links ADD COLUMN anti_audio INTEGER DEFAULT 0")
        cur.execute("ALTER TABLE anonymous_links ADD COLUMN anti_document INTEGER DEFAULT 0")
        cur.execute("ALTER TABLE anonymous_links ADD COLUMN anti_sticker INTEGER DEFAULT 0")
        db_conn.commit()

    security = get_anonymous_link_security(link_id)

    # گرفتن تنظیمات جدید
    cur.execute("""
        SELECT COALESCE(anti_media, 0), COALESCE(anti_photo, 0), COALESCE(anti_video, 0),
               COALESCE(anti_audio, 0), COALESCE(anti_document, 0), COALESCE(anti_sticker, 0)
        FROM anonymous_links WHERE id = ?
    """, (link_id,))
    row = cur.fetchone()

    if row:
        anti_media, anti_photo, anti_video, anti_audio, anti_document, anti_sticker = row
    else:
        anti_media = anti_photo = anti_video = anti_audio = anti_document = anti_sticker = 0

    text = f"🛡️ *تنظیمات امنیتی پیشرفته*\n\n"
    text += f"📝 لینک: *{link_name}*\n"
    text += "━━━━━━━━━━━━━━━━━━\n\n"
    text += "*🔞 محتوا:*\n"
    text += f"{'✅' if security['anti_nsfw'] else '❌'} ضد +18\n"
    text += f"{'✅' if security['anti_gore'] else '❌'} ضد خشونت\n"
    text += f"{'✅' if security['anti_badwords'] else '❌'} ضد فحش\n\n"
    text += "*📎 مدیا:*\n"
    text += f"{'✅' if anti_media else '❌'} همه مدیاها (غیرفعال همه)\n"
    text += f"{'✅' if anti_photo else '❌'} ضد عکس\n"
    text += f"{'✅' if anti_video else '❌'} ضد ویدیو\n"
    text += f"{'✅' if anti_audio else '❌'} ضد آهنگ/ویس\n"
    text += f"{'✅' if anti_document else '❌'} ضد فایل\n"
    text += f"{'✅' if anti_sticker else '❌'} ضد استیکر"

    keyboard = [
        [{"text": f"{'✅' if security['anti_nsfw'] else '❌'} ضد +18",
          "callback_data": f"anol_toggle_nsfw_{link_id}"}],
        [{"text": f"{'✅' if security['anti_gore'] else '❌'} ضد خشونت",
          "callback_data": f"anol_toggle_gore_{link_id}"}],
        [{"text": f"{'✅' if security['anti_badwords'] else '❌'} ضد فحش",
          "callback_data": f"anol_toggle_badwords_{link_id}"}],
        [{"text": f"{'✅' if anti_media else '❌'} غیرفعال همه مدیاها",
          "callback_data": f"anol_toggle_media_{link_id}"}],
        [{"text": f"{'✅' if anti_photo else '❌'} ضد عکس",
          "callback_data": f"anol_toggle_photo_{link_id}"},
         {"text": f"{'✅' if anti_video else '❌'} ضد ویدیو",
          "callback_data": f"anol_toggle_video_{link_id}"}],
        [{"text": f"{'✅' if anti_audio else '❌'} ضد آهنگ/ویس",
          "callback_data": f"anol_toggle_audio_{link_id}"},
         {"text": f"{'✅' if anti_document else '❌'} ضد فایل",
          "callback_data": f"anol_toggle_document_{link_id}"}],
        [{"text": f"{'✅' if anti_sticker else '❌'} ضد استیکر",
          "callback_data": f"anol_toggle_sticker_{link_id}"}],
        [{"text": "🔙 بازگشت به مدیریت لینک", "callback_data": f"anol_manage_{link_id}"}]
    ]

    if message_id:
        edit_inline_menu(chat_id, message_id, text, keyboard)
    else:
        send_inline_keyboard(chat_id, text, keyboard)

def _handle_trap_anon_reply(chat_id, user_id, text, msg, wait_info):
    """پردازش چت ناشناس از تله - کاملاً جدا از لینک‌های ناشناس"""
    from state import reply_waiting
    from database import conn as db_conn, get_user_display_name

    if text in ["لغو", "انصراف", "/cancel", "cancel"]:
        del reply_waiting[user_id]
        send(chat_id, "❌ ارسال پیام ناشناس لغو شد.")
        return True

    # ⭐ چک فحش (فقط لیست)
    if text:
        import os
        badwords_file = os.path.join(os.path.dirname(__file__), "..", "data", "badwords.txt")
        is_bad = False
        try:
            with open(badwords_file, "r", encoding="utf-8") as f:
                badwords_list = [line.strip().lower() for line in f if line.strip()]

            text_lower = text.lower()
            for badword in badwords_list:
                if badword in text_lower:
                    is_bad = True
                    break
        except:
            pass

        if is_bad:
            del reply_waiting[user_id]
            send(chat_id, "⛔ پاسخ شما حاوی کلمات نامناسب است و ارسال نشد.")
            return True

    # ⭐ چک NSFW و Gore برای چت تله
    if msg and (msg.get("photo") or msg.get("video") or msg.get("animation")):
        try:
            import os as _os
            import time as _time
            file_id = None
            if msg.get("photo"):
                file_id = msg["photo"][-1]["file_id"]
            elif msg.get("video"):
                file_id = msg["video"]["file_id"]
            elif msg.get("animation"):
                file_id = msg["animation"]["file_id"]

            if file_id:
                file_info = requests.get(f"{BASE_URL}getFile?file_id={file_id}").json()
                file_path = file_info.get("result", {}).get("file_path", "")
                if file_path:
                    download_url = f"https://tapi.bale.ai/file/bot262177859:Yln_PupSbSxRmopfmgYhUI1c1VaNWt2CmLU/{file_path}"
                    temp_dir = _os.path.join(_os.path.dirname(__file__), "..", "temp")
                    _os.makedirs(temp_dir, exist_ok=True)
                    ext = ".mp4" if msg.get("video") or msg.get("animation") else ".jpg"
                    local_path = _os.path.join(temp_dir, f"trap_nsfw_{user_id}_{_time.time()}{ext}")
                    r = requests.get(download_url, timeout=30)
                    with open(local_path, 'wb') as f:
                        f.write(r.content)

                    # چک NSFW
                    try:
                        from dataset.nsfw_detector import check_nsfw_from_path
                        nsfw_score = check_nsfw_from_path(local_path)
                        if nsfw_score > 0.7:
                            _os.remove(local_path)
                            del reply_waiting[user_id]
                            send(chat_id, "⛔ محتوای نامناسب (+18) قابل ارسال نیست.")
                            return True
                    except:
                        pass

                    # چک Gore
                    try:
                        from dataset.gore_vit_detector import check_gore_score_from_path
                        gore_score = check_gore_score_from_path(local_path)
                        if gore_score > 0.4:
                            _os.remove(local_path)
                            del reply_waiting[user_id]
                            send(chat_id, "⛔ محتوای خشونت‌آمیز قابل ارسال نیست.")
                            return True
                    except:
                        pass

                    try:
                        _os.remove(local_path)
                    except:
                        pass
        except:
            pass

    target_id = wait_info["target"]
    del reply_waiting[user_id]

    # ⭐ ناشناس مطلق - فقط بگو از طرف کیه
    sender_info = f"👤 پیام از طرف کسی که در تله‌اش افتادید"

    # ⭐ ذخیره پیام
    cur = db_conn.cursor()
    caption_text = text if text else ""
    media_type = "text"
    if msg:
        if msg.get("photo"): media_type = "PHOTO"
        elif msg.get("video"): media_type = "VIDEO"
        elif msg.get("animation"): media_type = "ANIMATION"
        elif msg.get("voice"): media_type = "VOICE"
        elif msg.get("sticker"): media_type = "STICKER"
        elif msg.get("document"): media_type = "DOCUMENT"

    sender_msg_id = msg.get("message_id", 0) if msg else 0

    cur.execute(
        "INSERT INTO anonymous_messages (from_user_id, message, chat_type, chat_id, sender_msg_id) VALUES (?, ?, 'private', ?, ?)",
        (user_id, f"[{media_type}] {caption_text}" if media_type != "text" else caption_text, target_id, sender_msg_id)
    )
    db_conn.commit()
    msg_id = cur.lastrowid

    # ⭐ دکمه‌ها (بدون ارسال به کانال)
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "👁️ خوندم", "callback_data": f"alink_seen_{msg_id}_{user_id}"},
                {"text": "↩️ پاسخ", "callback_data": f"alink_reply_{msg_id}_{user_id}"}
            ],
            [
                {"text": "⛔ مسدود", "callback_data": f"anon_open_panel_{msg_id}_{0}_{user_id}"},
                {"text": "😊 ری‌اکشن", "callback_data": f"alink_react_{msg_id}_{user_id}"}
            ]
        ]
    }

    # ⭐ پیام ۱
    api_call("sendMessage", json_data={
        "chat_id": target_id,
        "text": f"👻 پیام ناشناس داری!\n{sender_info} :"
    })

    # ⭐ پیام ۲
    result = send_any_media(
        target_id,
        msg or {"text": text},
        caption_prefix="",
        reply_markup=keyboard
    )

    if result.get("ok") and result.get("result", {}).get("message_id"):
        receiver_msg_id = result["result"]["message_id"]
        cur.execute(
            "UPDATE anonymous_messages SET sent_msg_id = ?, receiver_msg_id = ?, chat_id = ? WHERE id = ?",
            (receiver_msg_id, receiver_msg_id, target_id, msg_id)
        )
        db_conn.commit()

    # ⭐ تأیید برای فرستنده
    sender_keyboard = {
        "inline_keyboard": [
            [
                {"text": "✏️ ویرایش", "callback_data": f"alink_edit_{msg_id}_{user_id}"},
                {"text": "🗑️ حذف", "callback_data": f"anon_delete_self_{msg_id}_{user_id}"}
            ]
        ]
    }

    api_call("sendMessage", json_data={
        "chat_id": chat_id,
        "text": f"✅ پیام ناشناس ارسال شد!",
        "reply_markup": sender_keyboard,
        "reply_to_message_id": sender_msg_id if sender_msg_id else None
    })

    info(f"📨 پیام ناشناس (تله): {user_id} -> {target_id}")
    return True

# ==================== ویرایش پیام ====================

def handle_anonymous_edit_message(chat_id, user_id, text, msg=None):
    """پردازش ویرایش پیام ناشناس - پشتیبانی از ویرایش مدیا و کپشن"""
    from state import reply_waiting

    if user_id not in reply_waiting:
        return False

    wait_info = reply_waiting[user_id]

    if wait_info.get("type") != "alink_edit":
        return False

    if text in ["لغو", "انصراف", "cancel"]:
        del reply_waiting[user_id]
        send(chat_id, "❌ ویرایش لغو شد.")
        return True

    msg_id = wait_info.get("msg_id", 0)
    del reply_waiting[user_id]

    if not msg_id:
        send(chat_id, "❌ خطا: پیام اصلی پیدا نشد!")
        return True

    # ⭐ گرفتن اطلاعات پیام اصلی
    from database import conn as db_conn
    cur = db_conn.cursor()
    cur.execute(
        "SELECT receiver_msg_id, chat_id, message, from_user_id FROM anonymous_messages WHERE id = ? AND from_user_id = ?",
        (msg_id, user_id)
    )
    row = cur.fetchone()

    if not row:
        send(chat_id, "❌ پیام پیدا نشد یا شما فرستنده نیستید!")
        return True

    receiver_msg_id = row[0]
    target_chat_id = row[1]
    old_message = row[2]
    sender_id = row[3]

    # ⭐⭐ اگر target_chat_id معتبر نیست، از chat_id استفاده کن
    if not target_chat_id or target_chat_id == 0:
        target_chat_id = chat_id
        info(f"⚠️ target_chat_id خالی بود، از chat_id={chat_id} استفاده شد")

    # ⭐⭐ اگر target_chat_id با chat_id فعلی فرق داره، پیام اصلی در جای دیگه‌ایه
    # باید target_chat_id رو به جایی که پیام واقعاً هست تنظیم کنیم
    if target_chat_id != chat_id:
        # کاربر در جای دیگه‌ای ویرایش میکنه، باید target_chat_id رو به جایی که پیام هست ببریم
        # target_chat_id رو همون جایی که پیام هست نگه میداریم (برای ویرایش پیام اصلی)
        pass

    if not row:
        send(chat_id, "❌ پیام پیدا نشد یا شما فرستنده نیستید!")
        return True

    receiver_msg_id = row[0]
    target_chat_id = row[1]
    old_message = row[2]
    sender_id = row[3]

    if not receiver_msg_id or not target_chat_id:
        send(chat_id, "❌ پیام قابل ویرایش نیست (احتمالاً پاک شده)!")
        return True

    # ⭐ دکمه‌هایی که باید دوباره اضافه بشن
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "👁️ خوندم", "callback_data": f"alink_seen_{msg_id}_{sender_id}"},
                {"text": "↩️ پاسخ", "callback_data": f"alink_reply_{msg_id}_{sender_id}"}
            ],
            [
                {"text": "⛔ مسدود", "callback_data": f"anon_open_panel_{msg_id}_{0}_{sender_id}"},
                {"text": "😊 ری‌اکشن", "callback_data": f"alink_react_{msg_id}_{sender_id}"}
            ]
        ]
    }

    # ⭐ تشخیص نوع پیام اصلی
    original_was_media = old_message and ("[PHOTO]" in old_message or "[VIDEO]" in old_message or "[ANIMATION]" in old_message or "[VOICE]" in old_message or "[DOCUMENT]" in old_message or "[STICKER]" in old_message)
    has_new_media = msg and (msg.get("photo") or msg.get("video") or msg.get("animation") or msg.get("voice") or msg.get("document") or msg.get("sticker"))
    has_new_text = bool(text)

    # ⭐⭐ حالت ۱: متن → متن (editMessageText) ⭐⭐
    if has_new_text and not has_new_media and not original_was_media:
        try:
            result = requests.post(f"{BASE_URL}editMessageText", json={
                "chat_id": target_chat_id,
                "message_id": receiver_msg_id,
                "text": text + "\n\n🔄 _ویرایش شده_",
                "reply_markup": reply_markup
            }, timeout=5)

            if result.json().get("ok"):
                cur.execute("UPDATE anonymous_messages SET message = ? WHERE id = ?", (text, msg_id))
                db_conn.commit()

                # ⭐ دکمه‌های ویرایش و حذف رو به پیام اضافه کن
                edit_keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "✏️ ویرایش", "callback_data": f"alink_edit_{msg_id}_{user_id}"},
                            {"text": "🗑️ حذف", "callback_data": f"anon_delete_self_{msg_id}_{user_id}"}
                        ]
                    ]
                }

                # ⭐ ارسال دکمه‌های ویرایش به عنوان ریپلای به پیام ویرایش‌شده
                send(chat_id, "✏️ برای ویرایش دوباره روی دکمه کلیک کن", reply_to=receiver_msg_id)

                send(chat_id, "✅ پیام با موفقیت ویرایش شد!")
            else:
                send(chat_id, "❌ خطا در ویرایش پیام!")
        except Exception as e:
            error_log("edit_message", str(e))
            send(chat_id, f"❌ خطا در ویرایش: {str(e)[:80]}")
        return True

    # ⭐⭐ حالت ۲: مدیا (قدیمی) → کپشن جدید (editMessageCaption) ⭐⭐
    if original_was_media and has_new_text and not has_new_media:
        try:
            result = requests.post(f"{BASE_URL}editMessageCaption", json={
                "chat_id": target_chat_id,
                "message_id": receiver_msg_id,
                "caption": text + "\n\n🔄 _ویرایش شد_",
                "reply_markup": reply_markup
            }, timeout=5)

            if result.json().get("ok"):
                cur.execute("UPDATE anonymous_messages SET message = ? WHERE id = ?", (text, msg_id))
                db_conn.commit()

                # ⭐ دکمه‌های ویرایش و حذف رو به پیام اضافه کن
                edit_keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "✏️ ویرایش", "callback_data": f"alink_edit_{msg_id}_{user_id}"},
                            {"text": "🗑️ حذف", "callback_data": f"anon_delete_self_{msg_id}_{user_id}"}
                        ]
                    ]
                }

                # ⭐ ارسال دکمه‌های ویرایش به عنوان ریپلای به پیام ویرایش‌شده
                send(chat_id, "✏️ برای ویرایش دوباره روی دکمه کلیک کن", reply_to=receiver_msg_id)

                send(chat_id, "✅ کپشن با موفقیت ویرایش شد!")
            else:
                send(chat_id, "❌ خطا در ویرایش کپشن!")
        except Exception as e:
            error_log("edit_caption", str(e))
            send(chat_id, f"❌ خطا در ویرایش: {str(e)[:80]}")
        return True

    # ⭐⭐ حالت ۳: ویرایش خود مدیا + کپشن (editMessageMedia) ⭐⭐
    if has_new_media:
        try:
            # ⭐ تشخیص نوع مدیا جدید
            file_id = None
            media_type = None
            caption = text or ""

            if msg.get("photo"):
                file_id = msg["photo"][-1]["file_id"]
                media_type = "photo"
            elif msg.get("video"):
                file_id = msg["video"]["file_id"]
                media_type = "video"
            elif msg.get("animation"):
                file_id = msg["animation"]["file_id"]
                media_type = "animation"
            elif msg.get("voice"):
                file_id = msg["voice"]["file_id"]
                media_type = "voice"
            elif msg.get("document"):
                file_id = msg["document"]["file_id"]
                media_type = "document"
            elif msg.get("sticker"):
                file_id = msg["sticker"]["file_id"]
                media_type = "sticker"
            elif msg.get("audio"):
                file_id = msg["audio"]["file_id"]
                media_type = "audio"

            if not file_id or not media_type:
                send(chat_id, "❌ نوع فایل پشتیبانی نمی‌شود!")
                return True

            # ⭐ ساخت InputMedia بر اساس نوع مدیا
            input_media = None
            if media_type == "photo":
                input_media = {
                    "type": "photo",
                    "media": file_id,
                    "caption": caption + "\n\n🔄 _ویرایش شد_" if caption else "🔄 _ویرایش شد_"
                }
            elif media_type == "video":
                input_media = {
                    "type": "video",
                    "media": file_id,
                    "caption": caption + "\n\n🔄 _ویرایش شد_" if caption else "🔄 _ویرایش شد_"
                }
            elif media_type == "animation":
                input_media = {
                    "type": "animation",
                    "media": file_id,
                    "caption": caption + "\n\n🔄 _ویرایش شد_" if caption else "🔄 _ویرایش شد_"
                }
            elif media_type == "voice":
                input_media = {
                    "type": "audio",
                    "media": file_id,
                    "caption": caption + "\n\n🔄 _ویرایش شد_" if caption else "🔄 _ویرایش شد_"
                }
            elif media_type == "document":
                input_media = {
                    "type": "document",
                    "media": file_id,
                    "caption": caption + "\n\n🔄 _ویرایش شد_" if caption else "🔄 _ویرایش شد_"
                }
            elif media_type == "sticker":
                # ⭐ استیکر کپشن نداره و فقط با editMessageMedia قابل ویرایشه
                input_media = {
                    "type": "sticker",
                    "media": file_id
                }
            elif media_type == "audio":
                input_media = {
                    "type": "audio",
                    "media": file_id,
                    "caption": caption + "\n\n🔄 _ویرایش شد_" if caption else "🔄 _ویرایش شد_"
                }

            if not input_media:
                send(chat_id, "❌ نوع فایل پشتیبانی نمی‌شود!")
                return True

            # ⭐ ارسال درخواست editMessageMedia
            result = requests.post(f"{BASE_URL}editMessageMedia", json={
                "chat_id": target_chat_id,
                "message_id": receiver_msg_id,
                "media": input_media,
                "reply_markup": reply_markup
            }, timeout=10)

            if result.json().get("ok"):
                # ⭐ ذخیره در دیتابیس
                new_message_text = f"[{media_type.upper()}] {caption}" if caption else f"[{media_type.upper()}]"
                cur.execute("UPDATE anonymous_messages SET message = ? WHERE id = ?", (new_message_text, msg_id))
                db_conn.commit()

                # ⭐ دکمه‌های ویرایش و حذف رو به پیام اضافه کن
                edit_keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "✏️ ویرایش", "callback_data": f"alink_edit_{msg_id}_{user_id}"},
                            {"text": "🗑️ حذف", "callback_data": f"anon_delete_self_{msg_id}_{user_id}"}
                        ]
                    ]
                }

                # ⭐ ارسال دکمه‌های ویرایش به عنوان ریپلای به پیام ویرایش‌شده
                send(chat_id, "✏️ برای ویرایش دوباره روی دکمه کلیک کن", reply_to=receiver_msg_id)

                send(chat_id, "✅ مدیا با موفقیت ویرایش شد!")
            else:
                error_msg = result.json().get("description", "خطای ناشناخته")
                send(chat_id, f"❌ خطا در ویرایش مدیا: {error_msg[:80]}")
        except Exception as e:
            error_log("edit_media", str(e))
            send(chat_id, f"❌ خطا در ویرایش مدیا: {str(e)[:80]}")
        return True

    # ⭐⭐ حالت ۴: مدیا → حذف کپشن (ارسال متن خالی) ⭐⭐
    if original_was_media and not has_new_text and not has_new_media:
        try:
            result = requests.post(f"{BASE_URL}editMessageCaption", json={
                "chat_id": target_chat_id,
                "message_id": receiver_msg_id,
                "caption": "",
                "reply_markup": reply_markup
            }, timeout=5)

            if result.json().get("ok"):
                cur.execute("UPDATE anonymous_messages SET message = '' WHERE id = ?", (msg_id,))
                db_conn.commit()

                # ⭐ دکمه‌های ویرایش و حذف رو به پیام اضافه کن
                edit_keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "✏️ ویرایش", "callback_data": f"alink_edit_{msg_id}_{user_id}"},
                            {"text": "🗑️ حذف", "callback_data": f"anon_delete_self_{msg_id}_{user_id}"}
                        ]
                    ]
                }

                # ⭐ ارسال دکمه‌های ویرایش به عنوان ریپلای به پیام ویرایش‌شده
                send(chat_id, "✏️ برای ویرایش دوباره روی دکمه کلیک کن", reply_to=receiver_msg_id)

                send(chat_id, "✅ کپشن با موفقیت حذف شد!")
            else:
                send(chat_id, "❌ خطا در حذف کپشن!")
        except Exception as e:
            error_log("edit_caption_delete", str(e))
            send(chat_id, f"❌ خطا در حذف کپشن: {str(e)[:80]}")
        return True

    send(chat_id, "❌ لطفاً متن یا مدیا جدید را برای ویرایش ارسال کنید.")
    return True
