# handlers/safety_filter.py
"""
فیلتر محتوای خشن - نسخه نهایی
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'dataset'))
from dataset.gore_detector import check_gore_score, check_gore_score_from_path
from helpers import delete_message, send, send_permanent, handle_auto_warn, get_user_link, is_exempt_from_all_limits
from database import conn as db_conn
from logger import info, debug

def _ensure_table():
    c = db_conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS group_settings (chat_id INTEGER, key TEXT, value TEXT, PRIMARY KEY (chat_id, key))")
    db_conn.commit()

def is_gore_enabled(chat_id):
    _ensure_table()
    try:
        c = db_conn.cursor()
        c.execute("SELECT value FROM group_settings WHERE chat_id=? AND key='gore_enabled'", (chat_id,))
        row = c.fetchone()
        return row[0] == 'True' if row else False
    except Exception as e:
        pass
    return False

def set_gore_enabled(chat_id, enabled):
    _ensure_table()
    val = 'True' if enabled else 'False'
    c = db_conn.cursor()
    c.execute("INSERT OR REPLACE INTO group_settings (chat_id, key, value) VALUES (?, 'gore_enabled', ?)", (chat_id, val))
    db_conn.commit()

def is_test_gore_enabled(chat_id):
    _ensure_table()
    try:
        c = db_conn.cursor()
        c.execute("SELECT value FROM group_settings WHERE chat_id=? AND key='gore_test'", (chat_id,))
        row = c.fetchone()
        return row[0] == 'True' if row else False
    except:
        return False

def set_test_gore_enabled(chat_id, enabled):
    _ensure_table()
    val = 'True' if enabled else 'False'
    c = db_conn.cursor()
    c.execute("INSERT OR REPLACE INTO group_settings (chat_id, key, value) VALUES (?, 'gore_test', ?)", (chat_id, val))
    db_conn.commit()

def is_nsfw_enabled(chat_id):
    """چک کن NSFW در گروه فعال هست یا نه"""
    from database import conn as db_conn
    try:
        c = db_conn.cursor()
        c.execute("SELECT value FROM group_settings WHERE chat_id=? AND key='nsfw_enabled'", (chat_id,))
        row = c.fetchone()
        return row[0] == 'True' if row else False
    except:
        return False

def check_violence_content(chat_id, user_id, text, message_id, msg=None):
    if not msg:
        return False

    # گرفتن file_id از پیام
    file_id = None
    if msg.get("photo"):
        file_id = msg["photo"][-1]["file_id"]
    elif msg.get("video"):
        file_id = msg["video"]["file_id"]
    elif msg.get("animation"):
        file_id = msg["animation"]["file_id"]
    else:
        return False

    if not file_id:
        return False

    # فقط یک بار دانلود کن
    from download_manager import download_file
    local_path = download_file(file_id, "gore")

    if not local_path:
        return False

    try:
        # از مسیر محلی استفاده کن، نه دوباره دانلود
        from dataset.gore_detector import check_gore_score_from_path
        confidence = check_gore_score_from_path(local_path)
        confidence_pct = round(confidence * 100, 1)

        if is_test_gore_enabled(chat_id):
            if confidence_pct > 70:
                emoji, status = "🔴", "خشونت‌آمیز"
            elif confidence_pct > 40:
                emoji, status = "🟡", "مشکوک"
            else:
                emoji, status = "🟢", "عادی"
            send(chat_id, f"{emoji} *خشونت*\n👤 {get_user_link(user_id)}\n📊 درصد: {confidence_pct}%\n📌 وضعیت: {status}", reply_to=message_id)
            return True

        if is_gore_enabled(chat_id) and not is_exempt_from_all_limits(chat_id, user_id):
            if confidence_pct > 40:
                delete_message(chat_id, message_id)
                handle_auto_warn(chat_id, user_id, "gore")
                info(f"🩸 خشونت ({confidence_pct}%) از {user_id} در {chat_id} حذف شد")
                send_permanent(chat_id, f"🩸 {get_user_link(user_id)} محتوای خشن حذف شد و اخطار گرفت.")
                return True
    except Exception as e:
        debug(f"⚠️ خطا: {str(e)[:80]}")

    return False
