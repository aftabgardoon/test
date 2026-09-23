# handlers/private.py
"""
هندلر پیوی - فقط لینک ناشناس
"""
from helpers import send_permanent, send, api_call
from database import add_user
from config import START_TEXT
from handlers.private_menus import send_main_keyboard, clear_last_menu
from handlers.private_callbacks import _clear_history
from handlers.private_waiting import reset_all_states
from handlers.anonymous_link import (
    handle_anonymous_link, handle_anonymous_start, handle_anonymous_link_reply,
    handle_anonymous_reply_message, handle_anonymous_edit_message, show_anonymous_panel
)

# ⭐ حالت چت (برای سازگاری با بقیه ماژول‌ها)
_chat_mode = {}


def _restore_chat_modes():
    """بازیابی حالت چت - بدون قابلیت چت AI در این نسخه"""
    return 0


def _clear_user_states(user_id):
    """پاک کردن همه waiting state های کاربر"""
    from state import reply_waiting
    reply_waiting.pop(user_id, None)

    from handlers.private_waiting import (
        note_waiting, code_waiting, support_waiting, feedback_waiting,
        anonymous_waiting, ticket_waiting, donate_amount, donate_target
    )
    for d in [note_waiting, code_waiting, support_waiting, feedback_waiting,
              anonymous_waiting, ticket_waiting, donate_amount, donate_target]:
        d.pop(user_id, None)

    _chat_mode.pop(user_id, None)


def _handle_anonymous_waiting(chat_id, user_id, text, msg):
    """پردازش waiting state های مربوط به مدیریت لینک ناشناس"""
    from state import reply_waiting

    if user_id not in reply_waiting:
        return False

    wait_info = reply_waiting[user_id]
    wait_type = wait_info.get("type", "")

    # ⭐ ساخت لینک جدید - دریافت اسم
    if wait_type == "anol_new":
        if text in ["لغو", "انصراف", "/cancel", "cancel"]:
            del reply_waiting[user_id]
            send(chat_id, "❌ ساخت لینک لغو شد.")
            return True
        if text:
            if len(text) > 30:
                send(chat_id, "❌ اسم لینک نباید بیشتر از ۳۰ کاراکتر باشد!")
                return True
            from database import create_anonymous_link
            token = create_anonymous_link(user_id, text)
            del reply_waiting[user_id]

            from handlers.anonymous_link import _get_bot_username
            bot_username = _get_bot_username()
            link_url = f"https://ble.ir/{bot_username}?start=anon_{token}"

            send(chat_id, f"✅ لینک ناشناس *{text}* ساخته شد!\n\n🔗 لینک:\n`{link_url}`\n\n📌 برای دوستات بفرست تا ناشناس بهت پیام بدن.")
            show_anonymous_panel(chat_id, user_id)
            return True

    # ⭐ تغییر نام نمایشی
    elif wait_type == "anol_dname":
        if text in ["لغو", "انصراف", "/cancel", "cancel"]:
            del reply_waiting[user_id]
            send(chat_id, "❌ تغییر نام لغو شد.")
            return True
        if text:
            from database import set_user_display_name
            set_user_display_name(user_id, text)
            del reply_waiting[user_id]
            send(chat_id, f"✅ نام نمایشی شما به *{text}* تغییر کرد!")
            show_anonymous_panel(chat_id, user_id)
            return True

    # ⭐ تنظیم گروه برای لینک
    elif wait_type == "anol_setgroup":
        if text in ["لغو", "انصراف", "/cancel", "cancel"]:
            del reply_waiting[user_id]
            send(chat_id, "❌ تنظیم گروه لغو شد.")
            return True
        if text:
            group_input = text.strip().lstrip("@")

            chat_info = None
            try:
                chat_info = api_call("getChat", params={"chat_id": f"@{group_input}"})
            except:
                pass

            if not chat_info or not chat_info.get("ok"):
                try:
                    chat_id_num = int(group_input)
                    chat_info = api_call("getChat", params={"chat_id": chat_id_num})
                except:
                    pass

            if chat_info and chat_info.get("ok"):
                group_id = chat_info["result"]["id"]
                real_title = chat_info["result"].get("title", group_input)
            else:
                send(chat_id, "❌ گروه/کانال با این شناسه پیدا نشد!\n⚠️ اگه گروه خصوصیه، آیدی عددی رو بفرست.\n⚠️ ربات باید توی گروه عضو باشه.")
                return True

            reply_waiting[user_id] = {
                "type": "anol_setgroup_title",
                "link_id": wait_info.get("link_id", 0),
                "group_id": group_id,
                "real_title": real_title
            }

            keyboard = {
                "inline_keyboard": [
                    [{"text": f"✅ استفاده از اسم واقعی: {real_title}", "callback_data": f"anol_settitle_confirm_{real_title}"}],
                    [{"text": "❌ لغو", "callback_data": "cancel_waiting"}]
                ]
            }
            api_call("sendMessage", json_data={
                "chat_id": chat_id,
                "text": f"👥 گروه پیدا شد: *{real_title}* (`{group_id}`)\n\n📝 حالا یه اسم دلخواه برای نمایش انتخاب کن:\n(مثلاً: دوستان دانشگاه، بچه‌های پروژه)\n\nیا دکمه زیر رو بزن تا اسم واقعی گروه استفاده بشه:",
                "reply_markup": keyboard
            })
            return True

    # ⭐ تنظیم کانال برای لینک
    elif wait_type == "anol_setchannel":
        if text in ["لغو", "انصراف", "/cancel", "cancel"]:
            del reply_waiting[user_id]
            send(chat_id, "❌ تنظیم کانال لغو شد.")
            return True
        if text:
            channel_input = text.strip().lstrip("@")

            chat_info = None
            try:
                chat_info = api_call("getChat", params={"chat_id": f"@{channel_input}"})
            except:
                pass

            if not chat_info or not chat_info.get("ok"):
                try:
                    chat_id_num = int(channel_input)
                    chat_info = api_call("getChat", params={"chat_id": chat_id_num})
                except:
                    pass

            if chat_info and chat_info.get("ok"):
                channel_id = chat_info["result"]["id"]
                real_title = chat_info["result"].get("title", channel_input)
            else:
                send(chat_id, "❌ کانال با این شناسه پیدا نشد!")
                return True

            reply_waiting[user_id] = {
                "type": "anol_setchannel_title",
                "link_id": wait_info.get("link_id", 0),
                "channel_id": channel_id,
                "real_title": real_title
            }

            keyboard = {
                "inline_keyboard": [
                    [{"text": f"✅ استفاده از اسم واقعی: {real_title}", "callback_data": f"anol_setchanneltitle_confirm_{real_title}"}],
                    [{"text": "❌ لغو", "callback_data": "cancel_waiting"}]
                ]
            }
            api_call("sendMessage", json_data={
                "chat_id": chat_id,
                "text": f"📢 کانال پیدا شد: *{real_title}* (`{channel_id}`)\n\n📝 حالا یه اسم دلخواه برای نمایش انتخاب کن:",
                "reply_markup": keyboard
            })
            return True

    # ⭐ مرحله دوم تنظیم کانال - انتخاب اسم
    elif wait_type == "anol_setchannel_title":
        if text in ["لغو", "انصراف", "/cancel", "cancel"]:
            del reply_waiting[user_id]
            send(chat_id, "❌ تنظیم کانال لغو شد.")
            return True
        if text:
            channel_title = text.strip()
            channel_id = wait_info.get("channel_id", 0)
            link_id = wait_info.get("link_id", 0)

            from database import set_anonymous_link_channel
            if set_anonymous_link_channel(link_id, user_id, channel_id, channel_title):
                del reply_waiting[user_id]
                send(chat_id, f"✅ کانال *{channel_title}* (`{channel_id}`) برای لینک تنظیم شد!")
                show_anonymous_panel(chat_id, user_id)
            else:
                send(chat_id, "❌ خطا در تنظیم کانال!")
            return True

    # ⭐ مرحله دوم تنظیم گروه - انتخاب اسم
    elif wait_type == "anol_setgroup_title":
        if text in ["لغو", "انصراف", "/cancel", "cancel"]:
            del reply_waiting[user_id]
            send(chat_id, "❌ تنظیم گروه لغو شد.")
            return True
        if text:
            group_title = text.strip()
            group_id = wait_info.get("group_id", 0)
            link_id = wait_info.get("link_id", 0)

            from database import set_anonymous_link_group
            if set_anonymous_link_group(link_id, user_id, group_id, group_title):
                del reply_waiting[user_id]
                send(chat_id, f"✅ گروه *{group_title}* (`{group_id}`) برای لینک تنظیم شد!\n\nحالا پیام‌های این لینک توی گروه فرستاده میشه.")
                show_anonymous_panel(chat_id, user_id)
            else:
                send(chat_id, "❌ خطا در تنظیم گروه!")
            return True

    return False


def handle_private(chat_id, user_id, text, msg=None):
    # ⭐⭐⭐ اولویت اول: ورود از لینک ناشناس (/start anon_TOKEN) ⭐⭐⭐
    if text and text.startswith("/start anon_"):
        if handle_anonymous_start(chat_id, user_id, text, msg):
            return

    # ⭐⭐⭐ /start ⭐⭐⭐
    if text == "/start":
        _clear_user_states(user_id)
        reset_all_states(user_id, chat_id)
        _clear_history(user_id)
        clear_last_menu(user_id)
        add_user(user_id)
        send_permanent(chat_id, START_TEXT)
        send_main_keyboard(chat_id)
        return

    # ⭐⭐⭐ شروع مجدد / منوی اصلی ⭐⭐⭐
    if text in ["🔄 شروع مجدد", "🏠 منوی اصلی", "منوی اصلی"]:
        _clear_user_states(user_id)
        reset_all_states(user_id, chat_id)
        _clear_history(user_id)
        clear_last_menu(user_id)
        send_permanent(chat_id, "🔄 همه چیز ریست شد! به منوی اصلی برگشتی.")
        send_main_keyboard(chat_id)
        return

    # ⭐⭐⭐ لغو ⭐⭐⭐
    if text in ["لغو", "انصراف", "cancel", "/cancel"]:
        _clear_user_states(user_id)
        send(chat_id, "❌ عملیات لغو شد.")
        return

    # ⭐⭐⭐ ارسال پیام از لینک ناشناس ⭐⭐⭐
    if handle_anonymous_link_reply(chat_id, user_id, text, msg):
        return

    # ⭐⭐⭐ پاسخ به پیام ناشناس (صاحب لینک) ⭐⭐⭐
    if handle_anonymous_reply_message(chat_id, user_id, text, msg):
        return

    # ⭐⭐⭐ ویرایش پیام ناشناس ⭐⭐⭐
    if handle_anonymous_edit_message(chat_id, user_id, text, msg):
        return

    # ⭐⭐⭐ waiting state های مدیریت لینک ناشناس ⭐⭐⭐
    if _handle_anonymous_waiting(chat_id, user_id, text, msg):
        return

    # ⭐⭐⭐ دکمه لینک ناشناس ⭐⭐⭐
    if text in ["🔗 لینک ناشناس", "لینک ناشناس"]:
        _clear_user_states(user_id)
        handle_anonymous_link(chat_id, user_id, text, msg)
        return

    # ⭐⭐⭐ پیام ناشناخته ⭐⭐⭐
    send(chat_id, "🤔 متوجه نشدم!\nبرای استفاده از ربات، روی دکمه «🔗 لینک ناشناس» بزن.", reply_to=msg.get("message_id") if msg else None)
    send_main_keyboard(chat_id)
