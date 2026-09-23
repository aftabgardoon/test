# handlers/private_callbacks.py
"""
کالبک‌های منوی پیوی - فقط لینک ناشناس
"""
from helpers import (
    send_permanent, api_call, send, get_user_link,
    answer_callback, get_user_name
)
from config import BASE_URL
from handlers.private_menus import (
    send_main_keyboard, send_inline_menu, edit_inline_menu, delete_message,
    get_last_menu, clear_last_menu, set_last_menu
)
from handlers.private_waiting import reset_all_states
import requests

# ⭐ تاریخچه - یه لیست برای هر کاربر
_nav_history = {}


def _push_history(user_id, callback_data):
    if user_id not in _nav_history:
        _nav_history[user_id] = []
    _nav_history[user_id].append(callback_data)


def _pop_history(user_id):
    if user_id in _nav_history and _nav_history[user_id]:
        return _nav_history[user_id].pop()
    return None


def _clear_history(user_id):
    if user_id in _nav_history:
        _nav_history[user_id].clear()


def _show_menu_by_key(menu_key, chat_id, user_id, message_id):
    if menu_key == "anol_back":
        from handlers.anonymous_link import show_anonymous_panel
        show_anonymous_panel(chat_id, user_id, message_id)
    else:
        if message_id:
            try:
                delete_message(chat_id, message_id)
            except:
                pass
        send_main_keyboard(chat_id)


def handle_private_callback(callback_data, callback_id, user_id, message_id, chat_id, answer=True):
    """پردازش همه callback های پیوی - فقط لینک ناشناس"""

    if answer and not callback_data.startswith("unblock_"):
        try:
            requests.post(f"{BASE_URL}answerCallbackQuery", json={"callback_query_id": callback_id}, timeout=5)
        except:
            pass

    # ⭐⭐⭐ دکمه منوی اصلی ⭐⭐⭐
    if callback_data == "m_main":
        _clear_history(user_id)
        clear_last_menu(user_id)
        try:
            requests.post(f"{BASE_URL}deleteMessage", json={
                "chat_id": chat_id, "message_id": message_id
            }, timeout=5)
        except:
            pass
        send_main_keyboard(chat_id)
        return True

    # ⭐⭐⭐ دکمه بازگشت ⭐⭐⭐
    if callback_data == "nav_back":
        last_menu = get_last_menu(user_id)
        if last_menu:
            clear_last_menu(user_id)
            _show_menu_by_key(last_menu, chat_id, user_id, message_id)
            return True

        prev = _pop_history(user_id)
        if not prev:
            if message_id:
                try:
                    delete_message(chat_id, message_id)
                except:
                    pass
            send_main_keyboard(chat_id)
            return True

        _show_menu_by_key(prev, chat_id, user_id, message_id)
        return True

    # ⭐⭐⭐ لیست بلاکی ⭐⭐⭐
    if callback_data == "m_blocked":
        set_last_menu(user_id, "anol_back")
        from database import get_blocked_users, get_blocks_for_user_links, get_user_display_name

        blocked = get_blocked_users(user_id)
        link_blocks = get_blocks_for_user_links(user_id)
        for lb in link_blocks:
            if lb['blocked_user_id'] not in blocked:
                blocked.append(lb['blocked_user_id'])

        if blocked:
            text = "🚫 *لیست کاربران بلاک‌شده:*\n\n"
            text += "👆 روی هر کاربر بزن تا بلاک‌ش روی لینک‌ها رو مدیریت کنی:\n\n"
            buttons = []
            for b_id in blocked:
                name = get_user_display_name(b_id) or get_user_name(b_id) or f"کاربر {b_id}"
                text += f"• {name} (`{b_id}`)\n"
                buttons.append([{"text": f"⚙️ مدیریت {name}", "callback_data": f"blk_mgr_{b_id}"}])
                buttons.append([{"text": f"🗑️ آزاد کردن کامل {name}", "callback_data": f"unblock_{b_id}"}])
            buttons.append([{"text": "🔙 لینک ناشناس", "callback_data": "anol_back"}, {"text": "🏠 منوی اصلی", "callback_data": "m_main"}])
        else:
            text = "✅ هیچ کاربری بلاک نکردی!"
            buttons = [[{"text": "🔙 لینک ناشناس", "callback_data": "anol_back"}, {"text": "🏠 منوی اصلی", "callback_data": "m_main"}]]

        if message_id:
            edit_inline_menu(chat_id, message_id, text, buttons)
        else:
            send_inline_menu(chat_id, text, buttons)
        return True

    # ============ سیستم لینک ناشناس ============

    if callback_data == "anol_new":
        from state import reply_waiting
        reply_waiting[user_id] = {"type": "anol_new", "target": user_id}
        answer_callback(callback_id, "📝 اسم لینک رو وارد کن (مثلاً: دوستان، فامیل، همکلاسی‌ها)", True)
        api_call("sendMessage", json_data={
            "chat_id": chat_id,
            "text": "📝 *ساخت لینک ناشناس جدید*\n\nیه اسم برای لینکت انتخاب کن:\nمثلاً: دوستان، فامیل، همکلاسی‌ها\n\nاین اسم فقط برای خودت نمایش داده میشه.",
            "reply_markup": {"inline_keyboard": [[{"text": "❌ لغو", "callback_data": "cancel_waiting"}]]}
        })
        return True

    if callback_data == "anol_list":
        from handlers.anonymous_link import show_anonymous_links_list_panel
        show_anonymous_links_list_panel(chat_id, user_id, message_id)
        return True

    if callback_data == "anol_manage":
        from handlers.anonymous_link import show_manage_panel
        show_manage_panel(chat_id, user_id, message_id)
        return True

    if callback_data.startswith("anol_manage_"):
        try:
            link_id = int(callback_data.replace("anol_manage_", ""))
        except:
            answer_callback(callback_id, "❌ خطا!", True)
            return True
        from handlers.anonymous_link import show_manage_panel
        show_manage_panel(chat_id, user_id, message_id, link_id)
        return True

    if callback_data.startswith("anol_blocklist_"):
        link_id = int(callback_data.replace("anol_blocklist_", ""))
        from database import conn as db_conn, get_user_anonymous_links, get_user_display_name

        cur = db_conn.cursor()
        cur.execute("""
            SELECT blocked_user_id, created_at
            FROM anonymous_link_blocks
            WHERE link_id = ?
            ORDER BY created_at DESC
        """, (link_id,))
        blocks = cur.fetchall()

        links = get_user_anonymous_links(user_id)
        link_name = "ناشناس"
        for link in links:
            if link['id'] == link_id:
                link_name = link['link_name']
                break

        if not blocks:
            text = f"🚫 *لیست بلاکی لینک «{link_name}»*\n\n✅ هیچ کاربری بلاک نشده!"
            buttons = [[{"text": "🔙 بازگشت به مدیریت لینک", "callback_data": f"anol_manage_{link_id}"}]]
        else:
            text = f"🚫 *لیست بلاکی لینک «{link_name}»*\n\n"
            text += f"📊 تعداد: {len(blocks)} کاربر\n\n"
            buttons = []
            for block in blocks:
                blocked_id_db = block[0]
                name = get_user_display_name(blocked_id_db) or get_user_name(blocked_id_db) or f"کاربر {blocked_id_db}"
                text += f"• {name} (`{blocked_id_db}`)\n"
                buttons.append([{
                    "text": f"🔓 آزاد کردن {name}",
                    "callback_data": f"anol_unblock_{link_id}_{blocked_id_db}"
                }])
            buttons.append([{"text": "🔙 بازگشت به مدیریت لینک", "callback_data": f"anol_manage_{link_id}"}])

        if message_id:
            edit_inline_menu(chat_id, message_id, text, buttons)
        else:
            send_inline_menu(chat_id, text, buttons)
        return True

    if callback_data.startswith("anol_unblock_"):
        parts = callback_data.replace("anol_unblock_", "").split("_")
        link_id = int(parts[0])
        blocked_id = int(parts[1])

        from database import unblock_user_from_link, conn as db_conn, get_user_anonymous_links, get_user_display_name
        unblock_user_from_link(link_id, blocked_id)

        answer_callback(callback_id, "✅ کاربر آزاد شد!", True)

        cur = db_conn.cursor()
        cur.execute("""
            SELECT blocked_user_id, created_at
            FROM anonymous_link_blocks
            WHERE link_id = ?
            ORDER BY created_at DESC
        """, (link_id,))
        blocks = cur.fetchall()

        links = get_user_anonymous_links(user_id)
        link_name = "ناشناس"
        for link in links:
            if link['id'] == link_id:
                link_name = link['link_name']
                break

        if not blocks:
            text = f"🚫 *لیست بلاکی لینک «{link_name}»*\n\n✅ هیچ کاربری بلاک نشده!"
            buttons = [[{"text": "🔙 بازگشت به مدیریت لینک", "callback_data": f"anol_manage_{link_id}"}]]
        else:
            text = f"🚫 *لیست بلاکی لینک «{link_name}»*\n\n"
            text += f"📊 تعداد: {len(blocks)} کاربر\n\n"
            buttons = []
            for block in blocks:
                blocked_id_db = block[0]
                name = get_user_display_name(blocked_id_db) or get_user_name(blocked_id_db) or f"کاربر {blocked_id_db}"
                text += f"• {name} (`{blocked_id_db}`)\n"
                buttons.append([{
                    "text": f"🔓 آزاد کردن {name}",
                    "callback_data": f"anol_unblock_{link_id}_{blocked_id_db}"
                }])
            buttons.append([{"text": "🔙 بازگشت به مدیریت لینک", "callback_data": f"anol_manage_{link_id}"}])

        if message_id:
            edit_inline_menu(chat_id, message_id, text, buttons)
        else:
            send_inline_menu(chat_id, text, buttons)
        return True

    if callback_data == "anol_dname":
        from state import reply_waiting
        reply_waiting[user_id] = {"type": "anol_dname", "target": user_id}
        answer_callback(callback_id, "📝 نام نمایشی جدید رو وارد کن", True)
        api_call("sendMessage", json_data={
            "chat_id": chat_id,
            "text": "✏️ *تغییر نام نمایشی*\n\nاین نام به جای آیدی عددی برای گیرنده نمایش داده میشه.\n\n📝 نام جدید رو وارد کن:",
            "reply_markup": {"inline_keyboard": [[{"text": "❌ لغو", "callback_data": "cancel_waiting"}]]}
        })
        return True

    if callback_data == "anol_renew":
        from handlers.anonymous_link import show_manage_panel
        show_manage_panel(chat_id, user_id, message_id)
        return True

    if callback_data.startswith("anol_renew_"):
        try:
            link_id = int(callback_data.replace("anol_renew_", ""))
        except:
            answer_callback(callback_id, "❌ خطا!", True)
            return True

        from database import regenerate_anonymous_token, get_user_anonymous_links
        new_token = regenerate_anonymous_token(link_id, user_id)

        if new_token:
            from handlers.anonymous_link import show_manage_single_panel
            links = get_user_anonymous_links(user_id)
            for link in links:
                if link['id'] == link_id:
                    answer_callback(callback_id, "✅ لینک با موفقیت تمدید شد!", True)
                    show_manage_single_panel(chat_id, user_id, link, message_id)
                    return True

        answer_callback(callback_id, "❌ خطا در تمدید لینک!", True)
        return True

    if callback_data.startswith("anol_deact_"):
        try:
            link_id = int(callback_data.replace("anol_deact_", ""))
        except:
            return True

        from database import deactivate_anonymous_link, get_user_anonymous_links
        if deactivate_anonymous_link(link_id, user_id):
            from handlers.anonymous_link import show_manage_single_panel
            links = get_user_anonymous_links(user_id)
            for link in links:
                if link['id'] == link_id:
                    show_manage_single_panel(chat_id, user_id, link, message_id)
                    return True
        return True

    if callback_data.startswith("anol_reactivate_"):
        try:
            link_id = int(callback_data.replace("anol_reactivate_", ""))
        except:
            answer_callback(callback_id, "❌ خطا!", True)
            return True

        from database import regenerate_anonymous_token, get_user_anonymous_links
        new_token = regenerate_anonymous_token(link_id, user_id)

        if new_token:
            from handlers.anonymous_link import show_manage_single_panel
            links = get_user_anonymous_links(user_id)
            for link in links:
                if link['id'] == link_id:
                    answer_callback(callback_id, "🟢 لینک فعال شد!", True)
                    show_manage_single_panel(chat_id, user_id, link, message_id)
                    return True
        answer_callback(callback_id, "❌ خطا در فعال کردن لینک!", True)
        return True

    if callback_data.startswith("anol_delete_"):
        try:
            link_id = int(callback_data.replace("anol_delete_", ""))
        except:
            answer_callback(callback_id, "❌ خطا!", True)
            return True

        from database import conn as db_conn
        cur = db_conn.cursor()

        cur.execute("DELETE FROM anonymous_messages WHERE link_id = ?", (link_id,))
        cur.execute("DELETE FROM anonymous_link_blocks WHERE link_id = ?", (link_id,))
        cur.execute("DELETE FROM anonymous_links WHERE id = ? AND owner_id = ?", (link_id, user_id))
        db_conn.commit()

        from handlers.anonymous_link import show_anonymous_links_list_panel
        answer_callback(callback_id, "🗑️ لینک با موفقیت حذف شد!", True)
        show_anonymous_links_list_panel(chat_id, user_id, message_id)
        return True

    if callback_data.startswith("anol_setgroup_"):
        try:
            link_id = int(callback_data.replace("anol_setgroup_", ""))
        except:
            answer_callback(callback_id, "❌ خطا!", True)
            return True

        from state import reply_waiting
        reply_waiting[user_id] = {
            "type": "anol_setgroup",
            "link_id": link_id,
            "target": user_id
        }

        answer_callback(callback_id, "📝 شناسه گروه رو بفرست (مثلاً @MyGroup)", True)
        api_call("sendMessage", json_data={
            "chat_id": chat_id,
            "text": "👥 *تنظیم گروه برای لینک*\n\n📝 شناسه گروه رو بفرست:\n(مثلاً: @MyGroup یا MyGroup)\n\n⚠️ ربات باید توی گروه عضویت داشته باشه.",
            "reply_markup": {"inline_keyboard": [[{"text": "❌ لغو", "callback_data": "cancel_waiting"}]]}
        })
        return True

    if callback_data.startswith("anol_nogroup_"):
        try:
            link_id = int(callback_data.replace("anol_nogroup_", ""))
        except:
            answer_callback(callback_id, "❌ خطا!", True)
            return True

        from database import set_anonymous_link_group
        set_anonymous_link_group(link_id, user_id, 0, "")

        from handlers.anonymous_link import show_manage_panel
        answer_callback(callback_id, "✅ گروه حذف شد! پیام‌ها دوباره به پیوی میاد.", True)
        show_manage_panel(chat_id, user_id, message_id)
        return True

    if callback_data.startswith("anol_sec_"):
        try:
            link_id = int(callback_data.replace("anol_sec_", ""))
        except:
            answer_callback(callback_id, "❌ خطا!", True)
            return True

        from handlers.anonymous_link import show_link_security_panel
        show_link_security_panel(chat_id, user_id, link_id, message_id)
        answer_callback(callback_id, "🛡️ پنل امنیت باز شد", False)
        return True

    if callback_data.startswith("anol_toggle_"):
        parts = callback_data.replace("anol_toggle_", "").split("_")
        setting_type = parts[0]
        link_id = int(parts[1])

        from database import get_anonymous_link_security, set_anonymous_link_security, conn as db_conn

        if setting_type in ["nsfw", "badwords", "gore"]:
            security = get_anonymous_link_security(link_id)
            if setting_type == "nsfw":
                set_anonymous_link_security(link_id, "anti_nsfw", not security['anti_nsfw'])
            elif setting_type == "badwords":
                set_anonymous_link_security(link_id, "anti_badwords", not security['anti_badwords'])
            elif setting_type == "gore":
                set_anonymous_link_security(link_id, "anti_gore", not security['anti_gore'])
        else:
            cur = db_conn.cursor()
            cur.execute(f"SELECT COALESCE(anti_{setting_type}, 0) FROM anonymous_links WHERE id = ?", (link_id,))
            row = cur.fetchone()
            current = row[0] if row else 0
            new_val = 0 if current == 1 else 1

            if setting_type == "media":
                for st in ["photo", "video", "audio", "document", "sticker"]:
                    cur.execute(f"UPDATE anonymous_links SET anti_{st} = ? WHERE id = ?", (new_val, link_id))
            else:
                cur.execute(f"UPDATE anonymous_links SET anti_{setting_type} = ? WHERE id = ?", (new_val, link_id))
            db_conn.commit()

        from handlers.anonymous_link import show_link_security_panel
        show_link_security_panel(chat_id, user_id, link_id, message_id)
        answer_callback(callback_id, "🔄 بروز شد", False)
        return True

    if callback_data.startswith("anol_setchannel_"):
        try:
            link_id = int(callback_data.replace("anol_setchannel_", ""))
        except:
            answer_callback(callback_id, "❌ خطا!", True)
            return True

        from state import reply_waiting
        reply_waiting[user_id] = {
            "type": "anol_setchannel",
            "link_id": link_id,
            "target": user_id
        }

        answer_callback(callback_id, "📝 شناسه کانال رو بفرست (مثلاً @MyChannel)", True)
        api_call("sendMessage", json_data={
            "chat_id": chat_id,
            "text": "📢 *تنظیم کانال برای لینک*\n\n📝 شناسه کانال رو بفرست:\n(مثلاً: @MyChannel)\n\n⚠️ ربات باید توی کانال ادمین باشه.",
            "reply_markup": {"inline_keyboard": [[{"text": "❌ لغو", "callback_data": "cancel_waiting"}]]}
        })
        return True

    if callback_data.startswith("anol_nochannel_"):
        try:
            link_id = int(callback_data.replace("anol_nochannel_", ""))
        except:
            answer_callback(callback_id, "❌ خطا!", True)
            return True

        from database import set_anonymous_link_channel
        set_anonymous_link_channel(link_id, user_id, 0, "")

        from handlers.anonymous_link import show_manage_panel
        answer_callback(callback_id, "✅ کانال حذف شد!", True)
        show_manage_panel(chat_id, user_id, message_id)
        return True

    if callback_data.startswith("anol_setchanneltitle_confirm_"):
        real_title = callback_data.replace("anol_setchanneltitle_confirm_", "")

        from state import reply_waiting
        wait_info = reply_waiting.get(user_id, {})
        channel_id = wait_info.get("channel_id", 0)
        link_id = wait_info.get("link_id", 0)

        from database import set_anonymous_link_channel
        if set_anonymous_link_channel(link_id, user_id, channel_id, real_title):
            if user_id in reply_waiting:
                del reply_waiting[user_id]
            answer_callback(callback_id, f"✅ کانال با اسم واقعی «{real_title}» تنظیم شد!", True)
            from handlers.anonymous_link import show_anonymous_panel
            show_anonymous_panel(chat_id, user_id, message_id)
        else:
            answer_callback(callback_id, "❌ خطا در تنظیم کانال!", True)
        return True

    if callback_data.startswith("anol_settitle_confirm_"):
        real_title = callback_data.replace("anol_settitle_confirm_", "")

        from state import reply_waiting
        wait_info = reply_waiting.get(user_id, {})
        group_id = wait_info.get("group_id", 0)
        link_id = wait_info.get("link_id", 0)

        from database import set_anonymous_link_group
        if set_anonymous_link_group(link_id, user_id, group_id, real_title):
            if user_id in reply_waiting:
                del reply_waiting[user_id]
            answer_callback(callback_id, f"✅ گروه با اسم واقعی «{real_title}» تنظیم شد!", True)
            from handlers.anonymous_link import show_anonymous_panel
            show_anonymous_panel(chat_id, user_id, message_id)
        else:
            answer_callback(callback_id, "❌ خطا در تنظیم گروه!", True)
        return True

    if callback_data == "anol_copylist":
        from handlers.anonymous_link import show_copy_links_panel
        show_copy_links_panel(chat_id, user_id, message_id)
        return True

    if callback_data == "anol_messages":
        from handlers.anonymous_link import show_anonymous_messages_panel
        show_anonymous_messages_panel(chat_id, user_id, message_id=message_id)
        return True

    if callback_data.startswith("anol_messages_link_"):
        link_id = int(callback_data.replace("anol_messages_link_", ""))
        from handlers.anonymous_link import show_anonymous_messages_panel
        show_anonymous_messages_panel(chat_id, user_id, link_id, message_id)
        return True

    if callback_data.startswith("anol_msg_"):
        msg_id = int(callback_data.replace("anol_msg_", ""))
        from handlers.anonymous_link import show_anonymous_message_detail
        show_anonymous_message_detail(chat_id, user_id, msg_id, message_id)
        return True

    if callback_data.startswith("anol_copy_"):
        try:
            link_id = int(callback_data.replace("anol_copy_", ""))
        except:
            answer_callback(callback_id, "❌ خطا!", True)
            return True

        from database import get_user_anonymous_links
        links = get_user_anonymous_links(user_id)
        link_url = None
        link_name = "ناشناس"

        for link in links:
            if link['id'] == link_id:
                from handlers.anonymous_link import _get_bot_username
                bot_username = _get_bot_username()
                link_url = f"https://ble.ir/{bot_username}?start=anon_{link['token']}"
                link_name = link['link_name']
                break

        if link_url:
            answer_callback(callback_id, f"📋 لینک «{link_name}»:\n{link_url}", True)
        else:
            answer_callback(callback_id, "❌ لینک پیدا نشد!", True)
        return True

    if callback_data == "anol_back":
        from handlers.anonymous_link import show_anonymous_panel
        show_anonymous_panel(chat_id, user_id, message_id)
        return True

    # ============ مدیریت بلاک ============

    if callback_data.startswith("blk_mgr_"):
        blocked_id = int(callback_data.replace("blk_mgr_", ""))

        from database import get_user_anonymous_links, is_user_blocked_from_link, get_user_display_name

        links = get_user_anonymous_links(user_id)
        active_links = [l for l in links if l['is_active']]
        blocked_name = get_user_display_name(blocked_id) or get_user_name(blocked_id) or f"کاربر {blocked_id}"

        if not active_links:
            answer_callback(callback_id, "❌ هیچ لینک فعالی نداری!", True)
            return True

        text = f"⚙️ *مدیریت بلاک {blocked_name}*\n\n"
        text += f"👤 کاربر: `{blocked_id}`\n"
        text += "📋 لینک‌هایی که می‌خوای بلاک بمونه رو تیک بزن:\n"

        keyboard = []
        for link in active_links:
            is_blocked = is_user_blocked_from_link(link['id'], blocked_id)
            prefix = "✅ " if is_blocked else "⬜ "
            keyboard.append([{
                "text": f"{prefix}{link['link_name']}",
                "callback_data": f"blk_edit_{link['id']}_{blocked_id}"
            }])

        keyboard.append([{"text": "🔓 آزاد کردن از همه لینک‌ها", "callback_data": f"unblock_{blocked_id}"}])
        keyboard.append([{"text": "🔙 بازگشت به لیست بلاکی", "callback_data": "m_blocked"}])

        if message_id:
            edit_inline_menu(chat_id, message_id, text, keyboard)
        else:
            send_inline_menu(chat_id, text, keyboard)

        answer_callback(callback_id, f"⚙️ پنل مدیریت {blocked_name} باز شد", False)
        return True

    if callback_data.startswith("blk_edit_"):
        parts = callback_data.replace("blk_edit_", "").split("_")
        link_id = int(parts[0])
        blocked_id = int(parts[1])

        from database import is_user_blocked_from_link, block_user_from_link, unblock_user_from_link, get_user_anonymous_links, get_user_display_name

        if is_user_blocked_from_link(link_id, blocked_id):
            unblock_user_from_link(link_id, blocked_id)
        else:
            block_user_from_link(link_id, blocked_id)

        links = get_user_anonymous_links(user_id)
        active_links = [l for l in links if l['is_active']]
        blocked_name = get_user_display_name(blocked_id) or get_user_name(blocked_id) or f"کاربر {blocked_id}"

        text = f"⚙️ *مدیریت بلاک {blocked_name}*\n\n"
        text += f"👤 کاربر: `{blocked_id}`\n"
        text += "📋 لینک‌هایی که می‌خوای بلاک بمونه رو تیک بزن:\n"

        keyboard = []
        for link in active_links:
            is_blocked = is_user_blocked_from_link(link['id'], blocked_id)
            prefix = "✅ " if is_blocked else "⬜ "
            keyboard.append([{
                "text": f"{prefix}{link['link_name']}",
                "callback_data": f"blk_edit_{link['id']}_{blocked_id}"
            }])

        keyboard.append([{"text": "🔓 آزاد کردن از همه لینک‌ها", "callback_data": f"unblock_{blocked_id}"}])
        keyboard.append([{"text": "🔙 بازگشت به لیست بلاکی", "callback_data": "m_blocked"}])

        edit_inline_menu(chat_id, message_id, text, keyboard)
        answer_callback(callback_id, "🔄 بروز شد", False)
        return True

    if callback_data.startswith("unblock_"):
        try:
            requests.post(f"{BASE_URL}answerCallbackQuery", json={
                "callback_query_id": callback_id,
                "text": "✅ در حال آزادسازی...",
                "show_alert": False
            }, timeout=3)
        except:
            pass

        blocked_id = int(callback_data.replace("unblock_", ""))
        from database import unblock_user, get_blocked_users, get_user_display_name
        unblock_user(user_id, blocked_id)

        set_last_menu(user_id, "anol_back")
        blocked = get_blocked_users(user_id)

        if blocked:
            text = "🚫 *لیست کاربران بلاک‌شده:*\n\n"
            buttons = []
            for b_id in blocked:
                name = get_user_display_name(b_id) or get_user_name(b_id) or f"کاربر {b_id}"
                text += f"• {name} (`{b_id}`)\n"
                buttons.append([{"text": f"✅ آزاد کردن {name}", "callback_data": f"unblock_{b_id}"}])
            buttons.append([{"text": "🔙 لینک ناشناس", "callback_data": "anol_back"}, {"text": "🏠 منوی اصلی", "callback_data": "m_main"}])
        else:
            text = "✅ هیچ کاربری بلاک نکردی!"
            buttons = [[{"text": "🔙 لینک ناشناس", "callback_data": "anol_back"}, {"text": "🏠 منوی اصلی", "callback_data": "m_main"}]]

        try:
            edit_inline_menu(chat_id, message_id, text, buttons)
        except:
            try:
                requests.post(f"{BASE_URL}deleteMessage", json={
                    "chat_id": chat_id, "message_id": message_id
                }, timeout=5)
            except:
                pass
            send_inline_menu(chat_id, text, buttons)
        return True

    # ============ پنل مدیریت پیام ناشناس ============

    if callback_data.startswith("anon_open_panel_"):
        parts = callback_data.split("_")
        if len(parts) >= 5:
            msg_id = int(parts[3])
            link_id = int(parts[4])
            blocked_user_id = int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else 0

            panel_buttons = [
                [{"text": "📢 گزارش", "callback_data": f"anon_report_{msg_id}_{link_id}_{blocked_user_id}"}],
                [{"text": "🚫 بن از چت ناشناس", "callback_data": f"anon_block_chat_{msg_id}_{link_id}_{blocked_user_id}"}],
                [{"text": "🚷 بن از کانال", "callback_data": f"anon_block_channel_{msg_id}_{link_id}_{blocked_user_id}"}],
                [{"text": "🔙 بازگشت", "callback_data": f"anon_back_{msg_id}_{link_id}_{blocked_user_id}"}]
            ]

            try:
                requests.post(f"{BASE_URL}editMessageReplyMarkup", json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "reply_markup": {"inline_keyboard": panel_buttons}
                }, timeout=5)
            except:
                pass
        return True

    if callback_data.startswith("anon_report_"):
        from database import save_message_action, has_user_actioned, conn as db_conn
        from helpers import send_report_to_group
        parts = callback_data.split("_")
        if len(parts) >= 5:
            msg_id = int(parts[3])
            link_id = parts[4]
            blocked_user_id = int(parts[5]) if len(parts) > 5 else 0
            if has_user_actioned(msg_id, user_id, "report"):
                answer_callback(callback_id, "❌ قبلاً گزارش کردی!", True)
                return True
            save_message_action(msg_id, user_id, "report", link_id=link_id)
            cur = db_conn.cursor()
            cur.execute("SELECT message, from_user_id, sender_msg_id FROM anonymous_messages WHERE id = ?", (msg_id,))
            row = cur.fetchone()
            message_text = row[0] if row else ""
            real_blocked_id = blocked_user_id if blocked_user_id != 0 else row[1] if row else 0
            sender_msg_id = row[2] if row and len(row) > 2 else 0

            media_msg = None
            if sender_msg_id and sender_msg_id > 0:
                try:
                    result = api_call("getMessage", json_data={
                        "chat_id": real_blocked_id,
                        "message_id": sender_msg_id
                    })
                    if result.get("ok"):
                        media_msg = result.get("result", {})
                except:
                    pass

            send_report_to_group(chat_id, message_text, real_blocked_id, link_name=link_id, media_msg=media_msg)

            panel_buttons = [
                [{"text": "📢 گزارش ✅", "callback_data": "no_action"}],
                [{"text": "🚫 بن از چت ناشناس", "callback_data": f"anon_block_chat_{msg_id}_{link_id}_{blocked_user_id}"}],
                [{"text": "🚷 بن از کانال", "callback_data": f"anon_block_channel_{msg_id}_{link_id}_{blocked_user_id}"}],
                [{"text": "🔙 بازگشت", "callback_data": f"anon_back_{msg_id}_{link_id}_{blocked_user_id}"}]
            ]
            try:
                requests.post(f"{BASE_URL}editMessageReplyMarkup", json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "reply_markup": {"inline_keyboard": panel_buttons}
                }, timeout=5)
            except:
                pass
            answer_callback(callback_id, "✅ گزارش ارسال شد!", True)
        return True

    if callback_data.startswith("anon_block_chat_"):
        from database import save_message_action, has_user_actioned, block_user_from_link
        parts = callback_data.split("_")
        if len(parts) >= 5:
            msg_id = int(parts[3])
            link_id = int(parts[4]) if parts[4].isdigit() else 0
            blocked_user_id = int(parts[5]) if len(parts) > 5 else 0
            if not link_id or not blocked_user_id:
                answer_callback(callback_id, "❌ خطا در داده‌ها", True)
                return True
            if has_user_actioned(msg_id, user_id, "block_chat"):
                answer_callback(callback_id, "❌ قبلاً بن کردی!", True)
                return True
            save_message_action(msg_id, user_id, "block_chat", link_id=link_id)
            block_user_from_link(link_id, blocked_user_id)
            panel_buttons = [
                [{"text": "📢 گزارش", "callback_data": f"anon_report_{msg_id}_{link_id}_{blocked_user_id}"}],
                [{"text": "🚫 بن از چت ناشناس ✅", "callback_data": "no_action"}],
                [{"text": "🚷 بن از کانال", "callback_data": f"anon_block_channel_{msg_id}_{link_id}_{blocked_user_id}"}],
                [{"text": "🔙 بازگشت", "callback_data": f"anon_back_{msg_id}_{link_id}_{blocked_user_id}"}]
            ]
            try:
                requests.post(f"{BASE_URL}editMessageReplyMarkup", json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "reply_markup": {"inline_keyboard": panel_buttons}
                }, timeout=5)
            except:
                pass
            answer_callback(callback_id, "✅ کاربر از چت ناشناس بن شد!", True)
        return True

    if callback_data.startswith("anon_block_channel_"):
        from database import save_message_action, has_user_actioned, get_user_display_name
        from helpers import ban_user_from_channel, get_link_channel_id
        parts = callback_data.split("_")
        if len(parts) >= 5:
            msg_id = int(parts[3])
            link_id = int(parts[4]) if parts[4].isdigit() else 0
            blocked_user_id = int(parts[5]) if len(parts) > 5 else 0
            if not link_id or not blocked_user_id:
                answer_callback(callback_id, "❌ خطا در داده‌ها", True)
                return True
            if has_user_actioned(msg_id, user_id, "block_channel"):
                answer_callback(callback_id, "❌ قبلاً از کانال بن کردی!", True)
                return True
            channel_id = get_link_channel_id(link_id)
            if not channel_id or channel_id == 0:
                answer_callback(callback_id, "❌ برای این لینک کانالی تنظیم نشده!", True)
                return True

            save_message_action(msg_id, user_id, "block_channel", link_id=link_id)
            result = ban_user_from_channel(channel_id, blocked_user_id)

            if not result.get("ok"):
                answer_callback(callback_id, result.get("error", "❌ خطا در بن از کانال!"), True)
                panel_buttons = [
                    [{"text": "📢 گزارش", "callback_data": f"anon_report_{msg_id}_{link_id}_{blocked_user_id}"}],
                    [{"text": "🚫 بن از چت ناشناس", "callback_data": f"anon_block_chat_{msg_id}_{link_id}_{blocked_user_id}"}],
                    [{"text": "🚷 بن از کانال", "callback_data": f"anon_block_channel_{msg_id}_{link_id}_{blocked_user_id}"}],
                    [{"text": "🔙 بازگشت", "callback_data": f"anon_back_{msg_id}_{link_id}_{blocked_user_id}"}]
                ]
                try:
                    requests.post(f"{BASE_URL}editMessageReplyMarkup", json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "reply_markup": {"inline_keyboard": panel_buttons}
                    }, timeout=5)
                except:
                    pass
                return True

            panel_buttons = [
                [{"text": "📢 گزارش", "callback_data": f"anon_report_{msg_id}_{link_id}_{blocked_user_id}"}],
                [{"text": "🚫 بن از چت ناشناس", "callback_data": f"anon_block_chat_{msg_id}_{link_id}_{blocked_user_id}"}],
                [{"text": "🚷 بن از کانال ✅", "callback_data": "no_action"}],
                [{"text": "🔙 بازگشت", "callback_data": f"anon_back_{msg_id}_{link_id}_{blocked_user_id}"}]
            ]
            try:
                requests.post(f"{BASE_URL}editMessageReplyMarkup", json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "reply_markup": {"inline_keyboard": panel_buttons}
                }, timeout=5)
            except:
                pass
            answer_callback(callback_id, "✅ کاربر از کانال بن شد!", True)
        return True

    if callback_data.startswith("anon_back_"):
        from database import conn as db_conn

        parts = callback_data.split("_")

        if len(parts) >= 4:
            msg_id = int(parts[2])
            link_id = int(parts[3])
            blocked_user_id = int(parts[4]) if len(parts) > 4 else 0

            cur = db_conn.cursor()
            cur.execute("SELECT am.from_user_id, am.link_id FROM anonymous_messages am WHERE am.id = ?", (msg_id,))
            row = cur.fetchone()

            if row:
                from_user_id = row[0]
                link_id_db = row[1]

                cur.execute("SELECT channel_id, channel_title FROM anonymous_links WHERE id = ?", (link_id_db,))
                link_row = cur.fetchone()
                has_channel = False
                if link_row:
                    has_channel = link_row[0] is not None and link_row[0] != 0

                if has_channel:
                    main_buttons = [
                        [
                            {"text": "👁️ خوندم", "callback_data": f"alink_seen_{msg_id}_{from_user_id}"},
                            {"text": "💬 پاسخ ناشناس", "callback_data": f"alink_reply_{msg_id}_{from_user_id}"}
                        ],
                        [
                            {"text": "📢 ارسال به کانال", "callback_data": f"alink_tochannel_{msg_id}_{from_user_id}"}
                        ],
                        [
                            {"text": "⛔ مسدود", "callback_data": f"anon_open_panel_{msg_id}_{link_id_db}_{from_user_id}"},
                            {"text": "😊 ری‌اکشن", "callback_data": f"alink_react_{msg_id}_{from_user_id}"}
                        ]
                    ]
                else:
                    main_buttons = [
                        [
                            {"text": "👁️ خوندم", "callback_data": f"alink_seen_{msg_id}_{from_user_id}"},
                            {"text": "💬 پاسخ ناشناس", "callback_data": f"alink_reply_{msg_id}_{from_user_id}"}
                        ],
                        [
                            {"text": "⛔ مسدود", "callback_data": f"anon_open_panel_{msg_id}_{link_id_db}_{from_user_id}"},
                            {"text": "😊 ری‌اکشن", "callback_data": f"alink_react_{msg_id}_{from_user_id}"}
                        ]
                    ]

                try:
                    requests.post(f"{BASE_URL}editMessageReplyMarkup", json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "reply_markup": {"inline_keyboard": main_buttons}
                    }, timeout=5)
                except:
                    pass
            else:
                back_keyboard = {
                    "inline_keyboard": [
                        [{"text": "⛔ مسدود", "callback_data": f"anon_open_panel_{msg_id}_{link_id}_{blocked_user_id}"}]
                    ]
                }
                try:
                    requests.post(f"{BASE_URL}editMessageReplyMarkup", json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "reply_markup": back_keyboard
                    }, timeout=5)
                except:
                    pass
        return True

    # ============ عمومی ============

    if callback_data == "no_action":
        return True

    if callback_data == "cancel_waiting":
        reset_all_states(user_id, chat_id)
        clear_last_menu(user_id)
        try:
            delete_message(chat_id, message_id)
        except:
            pass
        answer_callback(callback_id, "❌ عملیات لغو شد", True)
        send(chat_id, "❌ عملیات لغو شد. به منوی اصلی برگشتی.")
        send_main_keyboard(chat_id)
        return True

    return False
