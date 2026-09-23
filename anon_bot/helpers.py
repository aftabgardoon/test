# helpers.py
import requests
import time
import threading
import re
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import BASE_URL, SPAM_LIMIT, SPAM_WINDOW, BLOCKED_DOMAINS, WHITE_LIST
from logger import info, success, warning, error, debug, user_action, admin_action, error_log
from settings import settings, get_group_setting, set_group_setting
import socket



# ====== Session با connection pool ======
_session = requests.Session()
# ⭐ غیرفعال کردن retry در سطح session (مدیریت retry توسط api_call انجام میشه)
_session.mount('https://', HTTPAdapter(max_retries=0, pool_connections=20, pool_maxsize=20))

# ====== Session با connection pool و refresh دوره‌ای ======
_last_session_refresh = time.time()
_session = None

def _get_session():
    global _session, _last_session_refresh

    if _session is None or time.time() - _last_session_refresh > 3600:
        if _session:
            try:
                _session.close()
            except:
                pass

        _session = requests.Session()
        # ⭐ غیرفعال کردن retry در سطح session (مدیریت retry توسط api_call انجام میشه)
        _session.mount('https://', HTTPAdapter(max_retries=0, pool_connections=20, pool_maxsize=20))

        # پاک کردن کش DNS
        try:
            socket.setdefaulttimeout(5)
        except:
            pass

        _last_session_refresh = time.time()

    return _session

# ====== لود فحش‌ها از فایل ======
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
BAD_WORDS_FILE = os.path.join(DATA_DIR, "badwords.txt")

def load_bad_words():
    if os.path.exists(BAD_WORDS_FILE):
        try:
            with open(BAD_WORDS_FILE, 'r', encoding='utf-8') as f:
                words = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            info(str(len(words)) + " کلمه فحش بارگذاری شد")
            return words
        except:
            return []
    else:
        default_words = ["fuck", "shit", "bitch", "asshole", "damn", "کیر", "کس", "کون", "جنده", "گوه"]
        try:
            with open(BAD_WORDS_FILE, 'w', encoding='utf-8') as f:
                f.write("\n".join(default_words))
        except:
            pass
        return default_words

BAD_WORDS = load_bad_words()

def api_call(method, params=None, json_data=None, retry_count=1):
    """
    فراخوانی API بله با قابلیت تلاش مجدد
    retry_count: تعداد تلاش‌های مجدد (پیش‌فرض ۱ بار)
    """
    url = f"{BASE_URL}{method}"
    last_error = None

    for attempt in range(retry_count + 1):  # +1 برای تلاش اول
        try:
            session = _get_session()
            if json_data:
                r = session.post(url, json=json_data, timeout=10)
            else:
                r = session.get(url, params=params, timeout=10)

            # ⭐ چک کن پاسخ خالی نباشه
            if not r.text or len(r.text.strip()) == 0:
                last_error = "Empty response from server"
                if attempt < retry_count:
                    time.sleep(1)
                    continue
                return {"ok": False, "description": last_error}

            # ⭐ چک کن که پاسخ JSON معتبر باشه
            try:
                result = r.json()
                # اگه موفق بود، برگردون
                if result.get("ok"):
                    return result
                # اگه ناموفق بود ولی خطای موقتی (مثل 500) بود، تلاش مجدد کن
                if result.get("error_code") in [500, 502, 503, 504]:
                    last_error = result.get("description", "Server error")
                    if attempt < retry_count:
                        time.sleep(1)
                        continue
                return result
            except:
                last_error = f"Invalid JSON response: {r.text[:100]}"
                if attempt < retry_count:
                    time.sleep(1)
                    continue
                return {"ok": False, "description": last_error}

        except Exception as e:
            last_error = str(e)
            error_log("api_call -> " + str(method), e)
            if attempt < retry_count:
                time.sleep(1)
                continue
            return {"ok": False, "description": last_error}

    return {"ok": False, "description": last_error or "Unknown error"}

def send(chat_id, msg, reply_to=None, retry_count=1, save_to_db=True):
    """ارسال پیام با قابلیت تلاش مجدد (پیش‌فرض ۱ بار) - save_to_db پیش‌فرض True شد"""
    try:
        data = {"chat_id": chat_id, "text": msg}
        if reply_to:
            data["reply_to_message_id"] = reply_to
        result = api_call("sendMessage", json_data=data, retry_count=retry_count)
        msg_id = result.get("result", {}).get("message_id")
        if msg_id:
            from logger import log_bot_response
            log_bot_response(chat_id, msg[:100])

            # ⭐ ذخیره message_id بات در دیتابیس (برای حذف) - همیشه ذخیره کن
            try:
                from database import conn as db_conn
                import time
                cur = db_conn.cursor()
                cur.execute("""
                    INSERT OR REPLACE INTO group_stats (chat_id, user_id, username, msg_type, message_id, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (chat_id, 262177859, "بات", "text", msg_id, int(time.time())))
                db_conn.commit()
                from logger import debug
                debug(f"💾 پیام بات {msg_id} در گروه {chat_id} ذخیره شد")
            except Exception as e:
                error_log("send_save_to_db", f"خطا در ذخیره پیام بات: {e}")
        return msg_id
    except Exception as e:
        error_log("send", f"خطا در ارسال پیام به {chat_id}: {e}")
        return None

def send_and_delete(chat_id, msg, delay=5, reply_to=None):
    msg_id = send(chat_id, msg, reply_to)
    if msg_id:
        threading.Thread(target=lambda: (time.sleep(delay), delete_message(chat_id, msg_id)), daemon=True).start()
    return msg_id

def delete_message(chat_id, message_id):
    """حذف یک پیام با شناسه - برگرداندن True/False با خطای دقیق"""
    try:
        result = api_call("deleteMessage", json_data={
            "chat_id": chat_id,
            "message_id": message_id
        })

        # اگه موفق بود
        if result.get("ok"):
            return True

        # اگه ناموفق بود، دلیل رو بررسی کن
        error_code = result.get("error_code")
        description = result.get("description", "")

        # پیام قبلاً پاک شده یا پیدا نشده - این خطا رو نادیده بگیر
        if error_code == 400 and ("message to delete not found" in description.lower() or
                                   "message_id_invalid" in description.lower() or
                                   "message can't be deleted" in description.lower()):
            # خطای ۴۰۰ با پیام پیدا نشد = قبلاً پاک شده
            return True  # برگردون True چون پیام دیگه وجود نداره

        # سایر خطاها رو لاگ کن
        from logger import error_log
        error_log("delete_message", f"خطا در حذف پیام {message_id}: code={error_code}, desc={description}")
        return False

    except Exception as e:
        from logger import error_log
        error_log("delete_message", f"خطا در حذف پیام {message_id}: {e}")
        return False

def send_permanent(chat_id, msg, reply_to=None):
    """ارسال پیام با تقسیم خودکار پیام‌های بلند - ذخیره در دیتابیس برای حذف"""
    try:
        if not msg or not isinstance(msg, str):
            return None

        max_len = 3900
        if len(msg) <= max_len:
            # ⭐ ذخیره در دیتابیس با save_to_db=True (پیش‌فرض True شد)
            return send(chat_id, msg, reply_to)

        total_parts = (len(msg) + max_len - 1) // max_len
        last_msg_id = None
        for i in range(total_parts):
            start = i * max_len
            part = msg[start:start + max_len]
            if part and part.strip():
                if i == 0:
                    last_msg_id = send(chat_id, part, reply_to, save_to_db=True)
                else:
                    last_msg_id = send(chat_id, "⬆️ ادامه پیام قبلی\n" + part, save_to_db=True)
        return last_msg_id
    except Exception as e:
        error_log("send_permanent", f"خطا: {e}")
        return None

def send_info(chat_id, msg, delay=10, reply_to=None):
    return send_and_delete(chat_id, msg, delay, reply_to)

def send_inline_keyboard(chat_id, text, buttons, reply_to=None, save_to_db=True):
    """ارسال پیام با دکمه‌های اینلاین - با استفاده از api_call"""
    keyboard = {"inline_keyboard": buttons}
    data = {"chat_id": chat_id, "text": text, "reply_markup": keyboard}
    if reply_to:
        data["reply_to_message_id"] = reply_to

    result = api_call("sendMessage", json_data=data)

    # ⭐ ذخیره در دیتابیس برای حذف - همیشه ذخیره کن
    if result.get("ok"):
        msg_id = result.get("result", {}).get("message_id")
        if msg_id:
            try:
                from database import conn as db_conn
                import time
                cur = db_conn.cursor()
                cur.execute("""
                    INSERT OR REPLACE INTO group_stats (chat_id, user_id, username, msg_type, message_id, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (chat_id, 262177859, "بات", "text", msg_id, int(time.time())))
                db_conn.commit()
                from logger import debug
                debug(f"💾 پیام اینلاین بات {msg_id} در گروه {chat_id} ذخیره شد")
            except Exception as e:
                error_log("send_inline_keyboard_save", f"خطا در ذخیره: {e}")

    return result

def delete_after(chat_id, message_id, delay):
    if message_id:
        threading.Thread(target=lambda: (time.sleep(delay), delete_message(chat_id, message_id)), daemon=True).start()

def edit_inline_menu(chat_id, message_id, text, buttons):
    """ویرایش پیام با دکمه‌های اینلاین - با استفاده از api_call"""
    from logger import info, error_log

    keyboard = {"inline_keyboard": buttons}
    try:
        result = api_call("editMessageText", json_data={
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "reply_markup": keyboard
        })

        # اگر ویرایش موفق بود
        if result.get("ok"):
            return True

        # اگر خطای 404 (پیام پیدا نشد) بود، پیام جدید بفرست
        if result.get("error_code") == 404 or "message not found" in str(result.get("description", "")):
            info(f"⚠️ پیام {message_id} در گروه {chat_id} پیدا نشد! ارسال پیام جدید...")

            # ارسال پیام جدید
            new_result = send_inline_keyboard(chat_id, text, buttons)
            if new_result and new_result.get("ok"):
                new_msg_id = new_result.get("result", {}).get("message_id")
                if new_msg_id:
                    # به‌روزرسانی message_id در دیتابیس
                    try:
                        from database import conn
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE bot_messages
                            SET message_id = ?
                            WHERE chat_id = ? AND msg_type = ?
                        """, (new_msg_id, chat_id, "panel_choice"))
                        conn.commit()
                        info(f"✅ message_id به‌روزرسانی شد: {new_msg_id}")
                    except Exception as e:
                        error_log("edit_inline_menu_update_msg_id", str(e))
                return True

        # سایر خطاها
        error_log("edit_inline_menu_failed", f"chat_id={chat_id}, msg_id={message_id}, result={result}")
        return False

    except Exception as e:
        error_log("edit_inline_menu", f"خطا: {e}")
        return False

def edit_message_text(chat_id, message_id, new_text):
    """ویرایش متن یک پیام"""
    try:
        result = api_call("editMessageText", json_data={
            "chat_id": chat_id,
            "message_id": message_id,
            "text": new_text
        })
        return result.get("ok", False)
    except:
        return False


def answer_callback(callback_id, text=None, show_alert=False):
    try:
        session = _get_session()
        data = {"callback_query_id": callback_id}
        if text:
            data["text"] = text
        if show_alert:
            data["show_alert"] = True
        session.post(f"{BASE_URL}answerCallbackQuery", json=data, timeout=5)
    except:
        pass


def get_count(chat_id):
    result = api_call("getChatMembersCount", params={"chat_id": chat_id})
    return result.get("result") if result.get("ok") else None


def can_control(chat_id, user_id):
    if user_id in WHITE_LIST:
        return True
    result = api_call("getChatAdministrators", params={"chat_id": chat_id})
    if result.get("ok") and result.get("result"):
        return any(admin.get("user", {}).get("id") == user_id for admin in result["result"])
    return False

def is_whitelist(user_id):
    return user_id in WHITE_LIST


def is_special_user(user_id):
    """VIP فروشگاهی - برای همه گروه‌ها"""
    from database import is_vip
    return is_vip(user_id)


def is_special_in_group(chat_id, user_id):
    """ویژه مدیری - فقط برای یک گروه"""
    if user_id is None:  # ⭐ اضافه کن
        return False
    from database import is_special_in_group as check_special
    return check_special(chat_id, user_id)


# ⭐⭐⭐ تابع جدید: معافیت کامل از همه محدودیت‌ها ⭐⭐⭐
def is_exempt_from_all_limits(chat_id, user_id):
    """کاربر کاملاً معاف از همه محدودیت‌هاست؟"""
    if user_id is None:  # ⭐ اضافه کن
        return False
    if user_id in WHITE_LIST:
        return True
    if is_special_user(user_id):
        return True
    if is_special_in_group(chat_id, user_id):
        return True
    if can_control(chat_id, user_id):
        return True
    return False


# ⭐ نگه داشتن تابع قدیمی برای سازگاری
def is_exempt_from_media_link(chat_id, user_id):
    return is_exempt_from_all_limits(chat_id, user_id)


def get_user_points(user_id):
    from database import get_points
    if user_id in WHITE_LIST:
        return "∞ (نامحدود)"
    return get_points(user_id)


def get_level(points):
    if points == "∞ (نامحدود)":
        return "👑 مدیر"
    if points < 50:
        return "🟢 مبتدی"
    elif points < 200:
        return "🔵 متوسط"
    elif points < 500:
        return "🟣 حرفه‌ای"
    elif points < 1000:
        return "🟠 استاد"
    elif points < 5000:
        return "👑 افسانه‌ای"
    else:
        return "🌟 اسطوره‌ای"


# ====== کش اسم کاربران ======
user_name_cache = {}

def get_user_link(user_id):
    """برگردوندن اسم کاربر با لینک uid:"""
    if user_id in user_name_cache:
        name, _ = user_name_cache[user_id]
    else:
        try:
            result = api_call("getChat", json_data={"chat_id": user_id})
            if result.get("ok"):
                chat_info = result.get("result", {})
                name = chat_info.get("first_name", "")
                username = chat_info.get("username", "")
                if not name:
                    name = str(user_id)
            else:
                name = str(user_id)
                username = ""
        except:
            name = str(user_id)
            username = ""
        user_name_cache[user_id] = (name, username)

    display_name = name if name else str(user_id)
    return f"[{display_name}](uid:{user_id})"


def get_bale_link(user_id):
    try:
        result = api_call("getChat", json_data={"chat_id": user_id})
        if result.get("ok"):
            chat = result.get("result", {})
            username = chat.get("username", "")
            name = chat.get("first_name", str(user_id))
            if username:
                return f"<a href='https://ble.ir/{username}' target='_blank' style='color:#fdcb6e;text-decoration:none;'>{name}</a>"
            return name or str(user_id)
    except:
        pass
    return str(user_id)


# ====== سیستم ضد اسپم ======
spam_tracker = {}

def check_spam(chat_id, user_id):
    if not get_group_setting(chat_id, "anti_spam", False):
        return False

    key = f"{chat_id}_{user_id}"
    now = time.time()
    if key not in spam_tracker:
        spam_tracker[key] = []

    spam_tracker[key] = [t for t in spam_tracker[key] if now - t < SPAM_WINDOW]
    spam_tracker[key].append(now)

    return len(spam_tracker[key]) > SPAM_LIMIT


# ====== سیستم ضد لینک ======
def has_blocked_link(chat_id, text):
    if not get_group_setting(chat_id, "anti_link", False):
        return False

    if not text:
        return False

    url_pattern = re.compile(r'https?://\S+|www\.\S+|t\.me/\S+')
    found_urls = url_pattern.findall(text.lower())

    if not found_urls:
        return False

    for url in found_urls:
        for domain in BLOCKED_DOMAINS:
            if domain in url:
                return True

    return True


# ====== سیستم ضد فحش ======
import re

def has_bad_words(chat_id, text):
    if not get_group_setting(chat_id, "anti_badwords", False):
        return False

    if not text:
        return False

    text_lower = text.lower()

    # ⭐ ایجاد الگوی regex برای تشخیص کلمات کامل و جدا
    # \b کلمه رو به صورت کامل و جدا چک میکنه
    for word in BAD_WORDS:
        # برای کلمات فارسی از \b استفاده نمیشه، باید خودمون جداکننده رو چک کنیم
        # الگو: کلمه با شروع خط یا فاصله یا جداکننده شروع بشه و با فاصله یا جداکننده یا پایان خط تموم بشه
        pattern = r'(?:^|\s|[،\.\!\؟\;\:\(\)\[\]\{\}])' + re.escape(word) + r'(?=\s|$|[،\.\!\؟\;\:\(\)\[\]\{\}])'

        if re.search(pattern, text_lower):
            return word

    return False


# ====== سیستم ضد کاراکترهای عجیب ======
def has_strange_chars(text):
    if not text:
        return False

    strange_ranges = [
        (0x0300, 0x036F),
        (0x0483, 0x0489),
        (0x12000, 0x1247F),
        (0x1B000, 0x1B0FF),
        (0xFE00, 0xFE0F),
        (0xE0100, 0xE01EF),
    ]

    strange_count = 0
    for char in text:
        code = ord(char)
        for start, end in strange_ranges:
            if start <= code <= end:
                strange_count += 1
                break

    if strange_count > len(text) * 0.3:
        return True

    return False


# ====== سیستم ضد رسانه ======
def is_photo_blocked(chat_id, msg):
    if not get_group_setting(chat_id, "anti_photo", False):
        return False
    return bool(msg.get("photo"))


def is_video_blocked(chat_id, msg):
    if not get_group_setting(chat_id, "anti_video", False):
        return False
    return bool(msg.get("video"))  # فقط ویدیو


# ====== محدودیت کاربران ======
def restrict_user(chat_id, user_id, can_send=False, duration=None):
    permissions = {
        "can_send_messages": can_send,
        "can_send_media_messages": can_send,
        "can_send_other_messages": can_send,
        "can_add_web_page_previews": can_send
    }
    payload = {"chat_id": chat_id, "user_id": user_id, "permissions": permissions}
    if duration:
        payload["until_date"] = int(time.time()) + duration
    return api_call("restrictChatMember", json_data=payload).get("ok", False)


def ban_user(chat_id, user_id):
    return api_call("banChatMember", json_data={"chat_id": chat_id, "user_id": user_id}).get("ok", False)


def unban_user(chat_id, user_id):
    return api_call("unbanChatMember", json_data={"chat_id": chat_id, "user_id": user_id}).get("ok", False)


def pin_message(chat_id, message_id):
    return api_call("pinChatMessage", json_data={"chat_id": chat_id, "message_id": message_id}).get("ok", False)


# ====== اخطار خودکار ======
# ====== اخطار خودکار ======
def handle_auto_warn(chat_id, user_id, violation_type):
    if not get_group_setting(chat_id, "auto_warn", False):
        return

    from database import set_warn, clear_warn_key, add_muted_user

    warn_count = set_warn(chat_id, user_id)

    violation_texts = {
        "spam": "اسپم",
        "link": "ارسال لینک",
        "badwords": "فحش",
        "photo": "عکس",
        "video": "ویدیو",
        "nsfw": "محتوای +18",  # ⭐ اینو اضافه کن
    }

    violation_fa = violation_texts.get(violation_type, "تخلف")
    max_warns = get_group_setting(chat_id, "max_warns", 3)
    mute_minutes = get_group_setting(chat_id, "mute_duration", 60)

    if warn_count >= max_warns:
        if get_group_setting(chat_id, "auto_mute", False):
            punishment = get_group_setting(chat_id, "punishment_type", "mute")

            if punishment == "ban":
                # 🚫 بن کردن کاربر
                ban_user(chat_id, user_id)
                try:
                    send_permanent(chat_id, "🚫 کاربر " + get_user_link(user_id) + " به دلیل " + str(max_warns) + " اخطار (" + violation_fa + ") بن شد!")
                except Exception as e:
                    error_log("handle_auto_warn", f"خطا در ارسال پیام بن: {e}")
            else:
                # 🔇 سکوت (مثل قبل)
                mute_seconds = mute_minutes * 60
                until_time = time.time() + mute_seconds
                restrict_user(chat_id, user_id, False, mute_seconds)
                add_muted_user(chat_id, user_id, until_time)

                if mute_minutes >= 60:
                    hours = mute_minutes // 60
                    mins = mute_minutes % 60
                    time_str = str(hours) + " ساعت" + (" و " + str(mins) + " دقیقه" if mins > 0 else "")
                else:
                    time_str = str(mute_minutes) + " دقیقه"

                try:
                    send_permanent(chat_id, "🔇 کاربر " + get_user_link(user_id) + " به دلیل " + str(max_warns) + " اخطار (" + violation_fa + ") به مدت " + time_str + " سکوت شد!")
                except Exception as e:
                    error_log("handle_auto_warn", f"خطا در ارسال پیام سکوت: {e}")

        clear_warn_key(str(chat_id) + "_" + str(user_id))
    else:
        remaining = max_warns - warn_count
        send_and_delete(chat_id, "⚠️ اخطار " + str(warn_count) + "/" + str(max_warns) + " به کاربر " + get_user_link(user_id) + "\nعلت: " + violation_fa + "\n" + str(remaining) + " اخطار تا سکوت", 7)

# ====== چک عضویت در کانال ======
def check_channel_membership(channel_id, user_id):
    result = api_call("getChatMember", json_data={
        "chat_id": channel_id,
        "user_id": user_id
    })

    if result.get("ok"):
        status = result.get("result", {}).get("status", "not_found")
        if status in ["member", "creator", "administrator"]:
            return status
        else:
            return "not_member"
    else:
        return "not_found"


def check_all_force_join_channels(chat_id, user_id):
    from database import get_force_join_channels

    channels = get_force_join_channels(chat_id)

    if not channels:
        return True, None

    for channel in channels:
        ch_id = channel["channel_id"]
        ch_title = channel["channel_title"]
        ch_link = channel["channel_link"]

        status = check_channel_membership(ch_id, user_id)

        if status in ["not_found", "not_member"]:
            return False, {
                "channel_id": ch_id,
                "channel_title": ch_title,
                "channel_link": ch_link,
                "status": status
            }

    return True, None

# آخر فایل helpers.py اضافه کن
# ====== ارسال خودکار هر نوع پیام ======
def send_any_media(chat_id, msg, caption_prefix="", reply_markup=None):
    """ارسال خودکار هر نوع پیام - عکس، ویدیو، گیف، ویس، استیکر، فایل، متن"""
    if not msg:
        return api_call("sendMessage", json_data={"chat_id": chat_id, "text": caption_prefix or "."})

    caption = msg.get("caption", "")
    full_caption = f"{caption_prefix}\n\n{caption}".strip() if caption_prefix and caption else (caption_prefix or caption or "")

    # عکس
    if msg.get("photo"):
        return api_call("sendPhoto", json_data={
            "chat_id": chat_id,
            "photo": msg["photo"][-1]["file_id"],
            "caption": full_caption,
            "reply_markup": reply_markup
        })

    # ویدیو
    elif msg.get("video"):
        return api_call("sendVideo", json_data={
            "chat_id": chat_id,
            "video": msg["video"]["file_id"],
            "caption": full_caption,
            "reply_markup": reply_markup
        })

    # گیف
    elif msg.get("animation"):
        return api_call("sendVideo", json_data={
            "chat_id": chat_id,
            "video": msg["animation"]["file_id"],
            "caption": full_caption,
            "reply_markup": reply_markup
        })

    # ویس
    elif msg.get("voice"):
        return api_call("sendVoice", json_data={
            "chat_id": chat_id,
            "voice": msg["voice"]["file_id"],
            "caption": full_caption,
            "reply_markup": reply_markup
        })

    # استیکر
    elif msg.get("sticker"):
        return api_call("sendSticker", json_data={
            "chat_id": chat_id,
            "sticker": msg["sticker"]["file_id"]
        })

    # فایل
    elif msg.get("document"):
        return api_call("sendDocument", json_data={
            "chat_id": chat_id,
            "document": msg["document"]["file_id"],
            "caption": full_caption,
            "reply_markup": reply_markup
        })

    # آهنگ
    elif msg.get("audio"):
        return api_call("sendAudio", json_data={
            "chat_id": chat_id,
            "audio": msg["audio"]["file_id"],
            "caption": full_caption,
            "reply_markup": reply_markup
        })

    # متن
    elif msg.get("text"):
        return api_call("sendMessage", json_data={
            "chat_id": chat_id,
            "text": full_caption or msg["text"],
            "reply_markup": reply_markup
        })

    # fallback
    return api_call("sendMessage", json_data={"chat_id": chat_id, "text": caption_prefix or "."})

def get_channel_id_from_username(username):
    """گرفتن آیدی کانال از یوزرنیم"""
    # پاکسازی یوزرنیم
    username = username.strip()
    if username.startswith("@"):
        username = username[1:]
    if username.startswith("https://t.me/"):
        username = username.replace("https://t.me/", "")
    if username.startswith("https://ble.ir/"):
        username = username.replace("https://ble.ir/", "")

    try:
        # تلاش برای گرفتن اطلاعات کانال
        result = api_call("getChat", params={"chat_id": f"@{username}"})
        if result.get("ok"):
            chat = result.get("result", {})
            return chat.get("id")
    except:
        pass

    # تلاش با آیدی عددی
    try:
        channel_id = int(username)
        result = api_call("getChat", params={"chat_id": channel_id})
        if result.get("ok"):
            return channel_id
    except:
        pass

    return None

def get_user_name(user_id):
    """فقط اسم کاربر رو برمیگردونه (بدون لینک)"""
    if user_id in user_name_cache:
        name, _ = user_name_cache[user_id]
        return name if name else str(user_id)

    try:
        result = api_call("getChat", json_data={"chat_id": user_id})
        if result.get("ok"):
            name = result.get("result", {}).get("first_name", "")
            username = result.get("result", {}).get("username", "")
            user_name_cache[user_id] = (name, username)
            return name if name else str(user_id)
    except:
        pass

    return str(user_id)  # ← این خط حتماً باشه

# ⭐⭐⭐ سیستم ضد اسپم پیوی ⭐⭐⭐
_pv_spam_tracker = {}
_pv_spam_blocked = {}

# ====== دریافت نام کاربری بات ======
_bot_username_cache = None
_bot_username_cache_time = 0

def get_bot_username():
    """دریافت نام کاربری بات با کش"""
    global _bot_username_cache, _bot_username_cache_time
    import time

    # کش ۱ ساعته
    if _bot_username_cache and time.time() - _bot_username_cache_time < 3600:
        return _bot_username_cache

    try:
        result = api_call("getMe")
        if result.get("ok"):
            username = result["result"].get("username", "")
            if username:
                _bot_username_cache = username
                _bot_username_cache_time = time.time()
                return username
    except:
        pass

    # fallback
    return "Meshkat8_bot"

def get_user_name(user_id):
    """فقط اسم کاربر رو برمیگردونه (بدون لینک)"""
    if user_id in user_name_cache:
        name, _ = user_name_cache[user_id]
        return name if name else str(user_id)

    try:
        result = api_call("getChat", json_data={"chat_id": user_id})
        if result.get("ok"):
            name = result.get("result", {}).get("first_name", "")
            username = result.get("result", {}).get("username", "")
            user_name_cache[user_id] = (name, username)
            return name if name else str(user_id)
    except:
        pass

    return str(user_id)

# ==================== توابع گزارش و بن ====================
def send_report_to_group(chat_id, message_text, from_user_id, link_name="", question_text="", media_msg=None):
    """ارسال گزارش به گروه گزارشات با پشتیبانی از مدیا"""
    from config import REPORT_GROUP
    import time

    user_link = get_user_link(from_user_id)
    user_name = get_user_name(from_user_id)

    # ساخت متن گزارش
    if question_text:
        report_text = f"""📢 *گزارش سوال صندلی داغ*

👤 کاربر: {user_link}
📝 سوال: {question_text}
🔗 لینک: {link_name}

📌 تاریخ: {time.strftime('%Y-%m-%d %H:%M:%S')}"""
    else:
        # پاک کردن برچسب مدیا از متن (اگه وجود داشته باشه)
        clean_text = message_text
        media_type = "متن"
        if message_text and (message_text.startswith("[PHOTO]") or
                            message_text.startswith("[VIDEO]") or
                            message_text.startswith("[ANIMATION]") or
                            message_text.startswith("[VOICE]") or
                            message_text.startswith("[DOCUMENT]") or
                            message_text.startswith("[STICKER]") or
                            message_text.startswith("[AUDIO]")):
            parts = message_text.split("]", 1)
            media_type = parts[0].replace("[", "").strip()
            if len(parts) > 1:
                clean_text = parts[1].strip()
            else:
                clean_text = ""

        report_text = f"""📢 *گزارش پیام ناشناس*

👤 کاربر: {user_link}
📎 نوع: {media_type}
📝 متن: {clean_text if clean_text else 'بدون متن'}
🔗 لینک: {link_name}

📌 تاریخ: {time.strftime('%Y-%m-%d %H:%M:%S')}"""

    if not REPORT_GROUP:
        return False

    # اگه مدیا داریم، مدیا رو با کپشن گزارش بفرست
    if media_msg:
        # ساخت کپشن کامل
        full_caption = report_text

        # ارسال مدیا با کپشن
        if media_msg.get("photo"):
            return api_call("sendPhoto", json_data={
                "chat_id": REPORT_GROUP,
                "photo": media_msg["photo"][-1]["file_id"],
                "caption": full_caption,
                "parse_mode": "Markdown"
            })
        elif media_msg.get("video"):
            return api_call("sendVideo", json_data={
                "chat_id": REPORT_GROUP,
                "video": media_msg["video"]["file_id"],
                "caption": full_caption,
                "parse_mode": "Markdown"
            })
        elif media_msg.get("animation"):
            return api_call("sendAnimation", json_data={
                "chat_id": REPORT_GROUP,
                "animation": media_msg["animation"]["file_id"],
                "caption": full_caption,
                "parse_mode": "Markdown"
            })
        elif media_msg.get("voice"):
            return api_call("sendVoice", json_data={
                "chat_id": REPORT_GROUP,
                "voice": media_msg["voice"]["file_id"],
                "caption": full_caption,
                "parse_mode": "Markdown"
            })
        elif media_msg.get("audio"):
            return api_call("sendAudio", json_data={
                "chat_id": REPORT_GROUP,
                "audio": media_msg["audio"]["file_id"],
                "caption": full_caption,
                "parse_mode": "Markdown"
            })
        elif media_msg.get("document"):
            return api_call("sendDocument", json_data={
                "chat_id": REPORT_GROUP,
                "document": media_msg["document"]["file_id"],
                "caption": full_caption,
                "parse_mode": "Markdown"
            })
        elif media_msg.get("sticker"):
            # استیکر کپشن نداره، پس اول استیکر رو بفرست، بعد متن گزارش
            api_call("sendSticker", json_data={
                "chat_id": REPORT_GROUP,
                "sticker": media_msg["sticker"]["file_id"]
            })
            return send_permanent(REPORT_GROUP, report_text)
        else:
            # مدیا شناسایی نشد، متن رو بفرست
            return send_permanent(REPORT_GROUP, report_text)

    # اگه مدیا نداریم، فقط متن رو بفرست
    return send_permanent(REPORT_GROUP, report_text)

def check_bot_permissions(chat_id, action=None, return_missing=False):
    """
    بررسی دسترسی‌های بات در گروه/کانال

    پارامترها:
        chat_id: آیدی گروه/کانال
        action: نوع عملیاتی که می‌خواهیم انجام دهیم (اختیاری)
        return_missing: اگر True باشد، لیست دسترسی‌های缺失 را برمی‌گرداند

    برمی‌گرداند:
        (has_permission, message, missing_list):
            has_permission: True/False
            message: پیام خطا در صورت عدم دسترسی
            missing_list: لیست دسترسی‌های缺失 (اگر return_missing=True)
    """
    missing_permissions = []

    try:
        # دریافت اطلاعات بات
        bot_info = api_call("getMe")
        if not bot_info.get("ok"):
            if return_missing:
                return False, "❌ خطا در دریافت اطلاعات بات!", []
            return False, "❌ خطا در دریافت اطلاعات بات!"

        bot_id = bot_info["result"]["id"]
        bot_name = bot_info["result"].get("first_name", "بات")

        # دریافت وضعیت بات در گروه
        member_result = api_call("getChatMember", json_data={
            "chat_id": chat_id,
            "user_id": bot_id
        })

        # ⭐ اگر بات در گروه عضو نیست
        if not member_result.get("ok"):
            msg = "⚠️ لطفاً بات را به عنوان *ادمین* انتخاب کنید و دسترسی‌های زیر را به آن بدهید:\n\n📋 *عضویت در گروه*\n📋 *ادمین بودن*"
            if return_missing:
                return False, msg, ["عضویت در گروه", "ادمین بودن"]
            return False, msg

        status = member_result.get("result", {}).get("status", "")

        # دسترسی‌های موجود در پاسخ API
        can_edit = member_result.get("result", {}).get("can_edit_messages", False)
        can_delete = member_result.get("result", {}).get("can_delete_messages", False)
        can_ban = member_result.get("result", {}).get("can_restrict_members", False)
        can_pin = member_result.get("result", {}).get("can_pin_messages", False)
        can_invite = member_result.get("result", {}).get("can_invite_users", False)
        can_change_info = member_result.get("result", {}).get("can_change_info", False)
        can_post_messages = member_result.get("result", {}).get("can_post_messages", False)

        # ⭐ اگر بات ادمین نباشد
        if status not in ["administrator", "creator"]:
            msg = "⚠️ لطفاً بات را به عنوان *ادمین* انتخاب کنید و دسترسی‌های زیر را به آن بدهید:\n\n📋 *ادمین بودن*"
            if return_missing:
                return False, msg, ["ادمین بودن"]
            return False, msg

        # ⭐ لیست دسترسی‌های مورد نیاز برای پنل مدیریت کامل
        # فقط دسترسی‌هایی که بات واقعاً به آنها نیاز دارد
        required_permissions = {
            "can_delete_messages": {"name": "حذف پیام‌ها", "value": can_delete},
            "can_restrict_members": {"name": "حذف اعضا", "value": can_ban},
            "can_pin_messages": {"name": "سنجاق پیام", "value": can_pin},
            "can_change_info": {"name": "ویرایش اطلاعات گروه", "value": can_change_info},
        }

        # can_edit_messages فقط برای کانال‌ها لازم است، برای گروه‌ها نه
        try:
            chat_info = api_call("getChat", json_data={"chat_id": chat_id})
            chat_type = chat_info.get("result", {}).get("type", "")
            if chat_type == "channel":
                required_permissions["can_edit_messages"] = {"name": "ویرایش پیام", "value": can_edit}
        except:
            pass

        # جمع‌آوری دسترسی‌های缺失
        for key, perm in required_permissions.items():
            if not perm["value"]:
                missing_permissions.append(perm["name"])

        # اگر عملیات خاصی درخواست شده، فقط همان دسترسی را چک کن
        if action == "delete":
            if not can_delete:
                msg = "⚠️ لطفاً دسترسی *حذف پیام‌ها* را به بات بدهید."
                if return_missing:
                    return False, msg, ["حذف پیام‌ها"]
                return False, msg
        elif action == "ban":
            if not can_ban:
                msg = "⚠️ لطفاً دسترسی *حذف اعضا* را به بات بدهید."
                if return_missing:
                    return False, msg, ["حذف اعضا"]
                return False, msg
        elif action == "pin":
            if not can_pin:
                msg = "⚠️ لطفاً دسترسی *سنجاق پیام* را به بات بدهید."
                if return_missing:
                    return False, msg, ["سنجاق پیام"]
                return False, msg
        elif action == "edit":
            if not can_edit:
                msg = "⚠️ لطفاً دسترسی *ویرایش پیام* را به بات بدهید."
                if return_missing:
                    return False, msg, ["ویرایش پیام"]
                return False, msg
        elif action == "change_info":
            if not can_change_info:
                msg = "⚠️ لطفاً دسترسی *ویرایش اطلاعات گروه* را به بات بدهید."
                if return_missing:
                    return False, msg, ["ویرایش اطلاعات گروه"]
                return False, msg

        # اگر دسترسی‌های缺失 وجود دارد
        if missing_permissions:
            missing_text = "، ".join(missing_permissions)
            msg = f"⚠️ لطفاً دسترسی‌های زیر را به بات بدهید:\n\n📋 *{missing_text}*"
            if return_missing:
                return False, msg, missing_permissions
            return False, msg

        return True, "✅ بات تمام دسترسی‌های لازم را دارد.", []

    except Exception as e:
        from logger import error_log
        error_log("check_bot_permissions", f"خطا: {e}")
        if return_missing:
            return False, f"❌ خطا در بررسی دسترسی بات: {str(e)[:100]}", []
        return False, f"❌ خطا در بررسی دسترسی بات: {str(e)[:100]}"

def ban_user_from_channel(channel_id, user_id):
    """بن کردن کاربر از کانال با مدیریت کامل خطا"""
    if not channel_id or channel_id == 0:
        return {"ok": False, "error": "کانالی تنظیم نشده است"}

    # ⭐ اول وضعیت کاربر در کانال رو چک کن
    try:
        member_result = api_call("getChatMember", json_data={
            "chat_id": channel_id,
            "user_id": user_id
        })
    except Exception as e:
        return {"ok": False, "error": f"خطا در دریافت اطلاعات کاربر: {str(e)}"}

    if not member_result.get("ok"):
        return {"ok": False, "error": "کاربر در کانال عضو نیست یا اطلاعاتی در دسترس نیست"}

    member_info = member_result.get("result", {})
    status = member_info.get("status", "")

    # ⭐ چک کن کاربر مالک کانال هست
    if status == "creator":
        return {"ok": False, "error": "❌ این کاربر مالک کانال است و قابل بن کردن نیست!"}

    # ⭐ چک کن کاربر مدیر کانال هست
    if status == "administrator":
        return {"ok": False, "error": "❌ این کاربر مدیر کانال است! ابتدا باید از مدیری خارج شود."}

    # ⭐ اگه کاربر عضو عادی هست، اقدام به بن کن
    if status in ["member", "restricted"]:
        try:
            result = api_call("banChatMember", json_data={
                "chat_id": channel_id,
                "user_id": user_id
            })
            if result.get("ok"):
                return {"ok": True, "message": "✅ کاربر با موفقیت از کانال بن شد!"}
            else:
                error_desc = result.get("description", "خطای ناشناخته")
                return {"ok": False, "error": f"❌ خطا در بن کردن: {error_desc}"}
        except Exception as e:
            return {"ok": False, "error": f"❌ خطا در بن کردن: {str(e)}"}

    # ⭐ کاربر وضعیت ناشناخته داره
    return {"ok": False, "error": f"❌ کاربر با وضعیت '{status}' قابل بن کردن نیست"}

def get_link_channel_id(link_id):
    """دریافت channel_id از لینک ناشناس یا صندلی داغ"""
    try:
        link_id = int(link_id)
    except:
        return 0
    from database import get_anonymous_link_channel_info
    channel_info = get_anonymous_link_channel_info(link_id)
    return channel_info.get("channel_id", 0) if channel_info else 0

def get_message(chat_id, message_id):
    """دریافت یک پیام با شناسه (برای گرفتن مدیا در گزارش)"""
    result = api_call("getMessage", json_data={
        "chat_id": chat_id,
        "message_id": message_id
    })
    return result.get("result") if result.get("ok") else None

def anti_spam_pv_mark(user_id):
    """ثبت یک درخواست از کاربر"""
    now = time.time()
    if user_id not in _pv_spam_tracker:
        _pv_spam_tracker[user_id] = []
    _pv_spam_tracker[user_id] = [t for t in _pv_spam_tracker[user_id] if now - t < 15]
    _pv_spam_tracker[user_id].append(now)

def anti_spam_pv_check(user_id):
    """چک کن کاربر اسپم کرده یا نه. اگه کرده، برگردون پیام محدودیت"""
    now = time.time()

    if user_id in _pv_spam_blocked:
        if now < _pv_spam_blocked[user_id]["until"]:
            return _pv_spam_blocked[user_id]["msg"]
        else:
            del _pv_spam_blocked[user_id]
            if user_id in _pv_spam_tracker:
                _pv_spam_tracker[user_id] = []

    if user_id in _pv_spam_tracker and len(_pv_spam_tracker[user_id]) >= 10:
        if user_id in _pv_spam_blocked:
            _pv_spam_blocked[user_id]["count"] += 1
        else:
            _pv_spam_blocked[user_id] = {"count": 1, "until": 0, "msg": ""}

        duration = 60 * (2 * (_pv_spam_blocked[user_id]["count"] - 1))
        _pv_spam_blocked[user_id]["until"] = now + duration

        if duration >= 3600:
            time_str = f"{duration // 3600} ساعت"
        elif duration >= 60:
            time_str = f"{duration // 60} دقیقه"
        else:
            time_str = f"{duration} ثانیه"

        msg = f"⛔ شما به دلیل اسپم برای {time_str} محدود شدید!\n🎯 دفعه: {_pv_spam_blocked[user_id]['count']}ام"
        _pv_spam_blocked[user_id]["msg"] = msg
        _pv_spam_tracker[user_id] = []

        info(f"🚫 ضداسپم پیوی: کاربر {user_id} برای {time_str} محدود شد (دفعه {_pv_spam_blocked[user_id]['count']}ام)")
        return msg

    return None

def check_bot_in_channel(channel_id):
    """چک کن بات در کانال عضو هست و مدیر هست یا نه"""
    from config import TOKEN
    try:
        # دریافت اطلاعات بات
        bot_info = api_call("getMe")
        if not bot_info.get("ok"):
            return {"ok": False, "error": "خطا در دریافت اطلاعات بات"}

        bot_id = bot_info["result"]["id"]

        # چک کردن وضعیت بات در کانال
        result = api_call("getChatMember", json_data={
            "chat_id": channel_id,
            "user_id": bot_id
        })

        if not result.get("ok"):
            return {"ok": False, "error": "بات در کانال عضو نیست"}

        status = result.get("result", {}).get("status", "")

        if status in ["creator", "administrator"]:
            # چک کن که دسترسی ارسال پیام داره
            if status == "administrator":
                can_post_messages = result.get("result", {}).get("can_post_messages", False)
                if not can_post_messages:
                    return {"ok": False, "error": "بات مدیر است اما دسترسی ارسال پیام را ندارد"}
            return {"ok": True, "status": status}
        else:
            return {"ok": False, "error": "بات در کانال مدیر نیست"}

    except Exception as e:
        return {"ok": False, "error": f"خطا: {str(e)}"}

def anti_spam_pv_is_blocked(user_id):
    """چک کن کاربر محدوده یا نه. برگردون پیام محدودیت"""
    now = time.time()
    if user_id in _pv_spam_blocked and now < _pv_spam_blocked[user_id]["until"]:
        return _pv_spam_blocked[user_id]["msg"]
    return None
