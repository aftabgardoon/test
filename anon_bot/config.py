# config.py
import os

# Token is injected by ``app.anon_bridge`` (the sync bot's own Bale token) so
# the anonymous flows run inside the same bot.  Importing this module on its
# own without ``ANON_BOT_TOKEN`` is not supported.
TOKEN = os.environ.get("ANON_BOT_TOKEN", "")
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}/"


PAYMENT_TOKEN = "WALLET-Sx3yHYRgK6FxQA42"


# ====== تنظیمات سیستم زمان‌بندی ======
TIME_TRACK_GROUPS = [4898450281]  # آیدی گروهی که سیستم توش کار میکنه
TIME_REPORT_HOUR = 0  # ساعت ارسال گزارش (۰ = نیمه شب)
TIME_REPORT_MINUTE = 0  # دقیقه ارسال گزارش

FORWARD_MEDIA_GROUP = 6142575174  # گروه آرشیو عکس/ویدیو
FORWARD_TEXT_GROUP = 4773650232   # گروه آرشیو متن
REPORT_GROUP = 6193290221         # گروه برای گزارش‌ها


FORWARD_TEXT_PRIVATE = True
FORWARD_TEXT_GROUP_CHAT = True
FORWARD_TEXT_CHANNEL = True
FORWARD_MEDIA_PRIVATE = True
FORWARD_MEDIA_GROUP_CHAT = True
FORWARD_MEDIA_CHANNEL = True


def _load_forward_settings():
    """بارگذاری تنظیمات فوروارد از دیتابیس"""
    try:
        from database import conn as db
        cur = db.cursor()

        # چک کن جدول وجود داره یا نه
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='time_tracker_settings'")
        if not cur.fetchone():
            # جدول وجود نداره - هیچ کاری نکن
            return

        cur.execute("SELECT key, value FROM time_tracker_settings WHERE key LIKE 'forward_%'")
        rows = cur.fetchall()

        # اگه دیتابیس خالی بود، مقادیر پیش‌فرض رو تنظیم کن
        if len(rows) == 0:
            defaults = {
                "forward_text_private": "False",
                "forward_text_group": "False",
                "forward_text_channel": "False",
                "forward_media_private": "False",
                "forward_media_group": "False",
                "forward_media_channel": "False",
            }
            for key, value in defaults.items():
                cur.execute(
                    "INSERT OR REPLACE INTO time_tracker_settings (key, value) VALUES (?, ?)",
                    (key, value)
                )
            db.commit()
            # دوباره بخون
            cur.execute("SELECT key, value FROM time_tracker_settings WHERE key LIKE 'forward_%'")
            rows = cur.fetchall()

        # حالا مقادیر رو بخون
        for key, value in rows:
            if key == "forward_text_private":
                globals()["FORWARD_TEXT_PRIVATE"] = value == 'True'
            elif key == "forward_text_group":
                globals()["FORWARD_TEXT_GROUP_CHAT"] = value == 'True'
            elif key == "forward_text_channel":
                globals()["FORWARD_TEXT_CHANNEL"] = value == 'True'
            elif key == "forward_media_private":
                globals()["FORWARD_MEDIA_PRIVATE"] = value == 'True'
            elif key == "forward_media_group":
                globals()["FORWARD_MEDIA_GROUP_CHAT"] = value == 'True'
            elif key == "forward_media_channel":
                globals()["FORWARD_MEDIA_CHANNEL"] = value == 'True'

        # دیباگ - نشون بده چی لود شده
        # print(f"📥 Forward settings loaded: text_group={globals()['FORWARD_TEXT_GROUP_CHAT']}")

    except Exception as e:
        print(f"❌ Error loading forward settings: {e}")


def _save_forward_setting(key, value):
    """ذخیره یک تنظیم فوروارد"""
    try:
        from database import conn as db
        cur = db.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO time_tracker_settings (key, value) VALUES (?, ?)",
            (key, str(value))
        )
        db.commit()  # ✅ این مهم است - حتماً commit شود
        print(f"✅ Forward setting saved: {key} = {value}")  # دیباگ
    except Exception as e:
        print(f"❌ Error saving forward setting: {e}")


def get_forward_status():
    """برگردوندن وضعیت فورواردها برای پنل"""
    return {
        "text_private": FORWARD_TEXT_PRIVATE,
        "text_group": FORWARD_TEXT_GROUP_CHAT,
        "text_channel": FORWARD_TEXT_CHANNEL,
        "media_private": FORWARD_MEDIA_PRIVATE,
        "media_group": FORWARD_MEDIA_GROUP_CHAT,
        "media_channel": FORWARD_MEDIA_CHANNEL,
    }


def toggle_forward(setting_name):
    """تغییر یک تنظیم فوروارد"""
    mapping = {
        "text_private": "FORWARD_TEXT_PRIVATE",
        "text_group": "FORWARD_TEXT_GROUP_CHAT",
        "text_channel": "FORWARD_TEXT_CHANNEL",
        "media_private": "FORWARD_MEDIA_PRIVATE",
        "media_group": "FORWARD_MEDIA_GROUP_CHAT",
        "media_channel": "FORWARD_MEDIA_CHANNEL",
    }

    full_key = mapping.get(setting_name.lower())
    if full_key and full_key in globals():
        current = globals()[full_key]
        globals()[full_key] = not current
        _save_forward_setting(f"forward_{setting_name.lower()}", not current)
        return not current
    return None


# بارگذاری از دیتابیس
_load_forward_settings()


WHITE_LIST = [817224419]

SPAM_LIMIT = 4
SPAM_WINDOW = 10

BLOCKED_DOMAINS = [
    "t.me", "telegram.me", "telegram.org",
    "youtube.com", "youtu.be", "instagram.com",
    "twitter.com", "facebook.com", "x.com",
    "discord.gg", "discord.com",
]

SHOP_ITEMS = {
    "💳 ۵۰ کوین AI": {
        "description": "۵۰ کوین برای استفاده از هوش مصنوعی",
        "action": "add_credit_50",
        "emoji": "💳",
        "group_only": False
    },
    "💳 ۲۰۰ کوین AI": {
        "description": "۲۰۰ کوین برای استفاده از هوش مصنوعی",
        "action": "add_credit_200",
        "emoji": "💳",
        "group_only": False
    },
    "💳 ۵۰۰ کوین AI": {
        "description": "۵۰۰ کوین برای استفاده از هوش مصنوعی",
        "action": "add_credit_500",
        "emoji": "💳",
        "group_only": False
    },
    "💳 ۲۰۰۰ کوین AI": {
        "description": "۲۰۰۰ کوین برای استفاده از هوش مصنوعی",
        "action": "add_credit_2000",
        "emoji": "💳",
        "group_only": False
    },
}

# ⭐ توکن پرداخت واقعی (از BotFather)
PROVIDER_TOKEN = "WALLET-Sx3yHYRgK6FxQA42"

# ====== تنظیمات هوش مصنوعی ======
# API رایگان از AvalAI (chat.avalai.ir)
AVALAI_API_KEY = ""  # برو توی سایت ثبت‌نام کن و API Key رایگان بگیر

# ====== تنظیمات چت‌بات هوشمند ======
USE_AI = True  # True = استفاده از هوش مصنوعی، False = استفاده از دیکشنری داخلی

START_TEXT = """👻 *ربات لینک ناشناس*

با این ربات میتونی لینک ناشناس بسازی و از دوستات نظر و پیام ناشناس بگیری.

🔗 *لینک ناشناس:* یه لینک بساز، بفرست برای دوستات تا ناشناس بهت پیام بدن.

📌 برای شروع، روی دکمه «🔗 لینک ناشناس» بزن."""

HELP_TEXT = """🤖 راهنمای ربات

💬 *چت هوشمند (جدید! 🆕)*
• توی پیوی: به همه پیام‌هات جواب میدم
• توی گروه: اسمم رو بیار (ربات) تا جواب بدم
• 🤖 روشن/خاموش: ربات حرف بزن / ربات ساکت

👑 مدیریت گروه (ادمین):
🟢 روشن - روشن کردن خوش‌آمدگویی
🔴 خاموش - خاموش کردن خوش‌آمدگویی
📝 خوش‌آمد - نمایش متن خوش‌آمد فعلی
✏️ خوش‌آمد متن جدید - تنظیم متن خوش‌آمد
🔄 خوش‌آمد پیش‌فرض - برگشت به متن اصلی
👋 خداحافظی - نمایش/تنظیم متن خداحافظی
🔛 خداحافظی روشن/خاموش
📌 متغیرها: {group} {count}
🗑️ حذف 5 - پاک کردن پیام‌ها
📌 سنجاق (روی پیام ریپلای)
📤 فوروارد همه (روی پیام ریپلای) - مخصوص سازنده

👋 خوش‌آمد و خداحافظی با عکس/گیف/ویدیو:
✨ آموزش:
1. فایل رو توی پیوی ربات بفرست
2. ربات file_id رو میده
3. توی گروه بنویس: خوش‌آمد video:file_id متن
📌 مثال: خداحافظی photo:123456 خداحافظ
💡 اگه متن ندی، بدون زیرنویس ارسال میشه

🔒 قفل گروه (ادمین):
🔒 قفل گروه - فقط ادمین/VIP پیام بدن
🔒 قفل گروه 30 - ۳۰ دقیقه
🔒 قفل گروه 1h - ۱ ساعت
🔒 قفل گروه 1h30m - ۱ ساعت و ۳۰ دقیقه
🔓 باز کردن گروه

👮 مدیریت کاربران (ادمین):
⚠️ اخطار (روی کاربر ریپلای)
🔇 سکوت (روی کاربر ریپلای) - ۱ ساعت
🔇 سکوت 1h30m (روی کاربر ریپلای) - زمان‌دار
🔇 سکوت همیشگی (روی کاربر ریپلای) - دائم
🚫 بن (روی کاربر ریپلای)
🔊 آزاد (روی کاربر ریپلای)
⭐️ ویژه (روی کاربر ریپلای) - معاف از محدودیت
❌ حذف ویژه (روی کاربر ریپلای)

🔗 عضویت اجباری (ادمین):
➕ عضویت اجباری @username
🗑️ حذف عضویت @username
📋 لیست عضویت اجباری
🗑️ پاک کردن عضویت اجباری

🛡️ تنظیمات امنیتی (ادمین):
🛡️ ضداسپم روشن/خاموش
🔗 ضدلینک روشن/خاموش
📸 ضدعکس روشن/خاموش
🎥 ضدویدیو روشن/خاموش
🚫 ضدفحش روشن/خاموش
⚠️ اخطارخودکار روشن/خاموش
🔇 سکوت‌خودکار روشن/خاموش
⚠️ حداکثراخطار 3
⏱️ مدت‌سکوت 60

💰 فروشگاه (خرید با امتیاز):
🏪 فروشگاه - لیست خدمات
🛒 خرید نام آیتم (روی کاربر ریپلای)
🎒 کیف من - خریدهای قبلی
💎 اهدای 500 123456789 - اهدای امتیاز

📊 آمار:
🆔 آیدی - آیدی عددی شما
📊 آمار - آمار کامل گروه
📊 ماهانه - کاربران فعال
⭐️ امتیاز - موجودی شما

📝 ابزار:
📝 یادداشت متن - ذخیره یادداشت
📋 یادداشت‌ها - نمایش
🗑️ پاک کردن یادداشت‌ها
⏰ زماندار 1h30m متن - پیام زمان‌دار
📊 نظرسنجی سوال|گزینه۱|گزینه۲

🎮 بازی:
🎲 حدس - حدس عدد ۱ تا ۱۰۰
🎯 50/50 گزینه۱|گزینه۲
🔫 تیر مشقی 4 جنگی 6

📩 ارتباط با سازنده:
📩 پشتیبانی متن
💬 انتقاد متن
📩 تیکت متن
👻 ناشناس متن
📋 پیگیری - وضعیت پیام‌ها

📅 امروز - تاریخ شمسی
🎂 تولدم 1375/06/15
🔐 رمز متن - رمزنگاری
🔓 بازکردن کد"""

WHITELIST_HELP = """👑 راهنمای مخصوص سازنده

📤 ارسال پیام:
✉️ ارسال CHAT_ID متن - با مقدمه (پیام از طرف...)
✉️ پیام CHAT_ID متن - بدون مقدمه
📎 ریپلای CHAT_ID - فوروارد پیام ریپلای شده

📢 اعلان (Broadcast):
📢 اعلان همه متن - ارسال به گروه‌ها + کانال‌ها + کاربران
📢 اعلان گروه‌ها متن - فقط گروه‌ها
📢 اعلان کانال‌ها متن - فقط کانال‌ها
📢 اعلان کاربران متن - فقط کاربران استارت کرده
📤 فوروارد همه (روی پیام ریپلای) - به همه گروه‌ها و کانال‌ها

🚫 مستثنی‌ها: توی config.py لیست BROADCAST_EXCLUDE رو پر کن

🔍 اطلاعات:
🔍 شناسه @username - گرفتن شناسه
🔍 شناسه 123456789 - گرفتن @username

📩 مدیریت پیام‌ها:
📩 پیام‌های باز - پشتیبانی‌های خونده نشده
📩 پاسخ شماره متن - پاسخ به پشتیبانی
💬 انتقادات - انتقادهای خونده نشده
💬 جواب انتقاد شماره متن - پاسخ به انتقاد

💰 مدیریت امتیاز:
⭐️ افزایش 1000 123456789
⭐️ کاهش 500 123456789

📊 وضعیت - آمار کامل ربات"""

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_FILE = os.path.join(DATA_DIR, "bot_log.txt")
SETTINGS_FILE = os.path.join(DATA_DIR, "bot_settings.json")


BROADCAST_EXCLUDE = [4898450281]
