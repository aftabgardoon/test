# settings.py
import json
import os
from logger import info, error


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
SETTINGS_FILE = os.path.join(DATA_DIR, "bot_settings.json")


def get_default_group_settings():
    return {
        "welcome_status": True,
        "welcome_text": "🎉 یه عضو جدید به گروه اضافه شد!\nخوش اومدی 🌹",
        "goodbye_status": True,
        "goodbye_text": "👋 یکی از اعضا از گروه خارج شد!\n💔 دلمون برات تنگ میشه...",
        "anti_spam": False,
        "anti_link": False,
        "anti_photo": False,
        "anti_video": False,
        "anti_badwords": False,
        "anti_strange_chars": True,
        "auto_warn": False,
        "auto_mute": False,
        "max_warns": 3,
        "mute_duration": 60,
        "is_locked": False,
        "anti_bot": False,  # ⭐ این خط رو اضافه کن
        "punishment_type": "mute",
        "anti_nsfw": False,   # ضد محتوای +18
        "anti_gore": False,   # ضد خشونت
        "anti_toxic": False,  # ضد توهین
        "anti_media": False,  # ضد مدیا
        "anti_username": False,  # قفل یوزرنیم
        "anti_text": False,  # قفل متن
        "anti_animation": False,  # قفل گیف
        "anti_document": False,  # قفل فایل
        "anti_forward": False,  # قفل فوروارد
        "anti_reply": False,  # قفل ریپلای
        "anti_hashtag": False,  # قفل هشتگ
        "anti_contact": False,  # قفل مخاطب
        "anti_audio": False,  # قفل صدا
        "anti_voice": False,  # قفل ویس
        "anti_location": False,  # قفل لوکیشن
        "anti_english": False,  # قفل اینگلیسی
        "anti_sticker": False,  # قفل استیکر
        "games_lock": False,  # قفل بازی‌ها
        "level_system": False,  # سیستم لول
        "level_up_notify": False,  # اعلان لول آپ
        "fortune_lock": False,  # قفل فال
        "calendar_lock": False,  # قفل تقویم
        "secret_msg_lock": False,  # قفل پیام مخفی
        "join_forced": False,  # جوین اجباری
        "admin_forced": False,  # اد اجباری
        "char_limit": False,  # قفل کاراکتر
        "bio_link_lock": False,  # قفل لینک بیو
        "edit_lock": False,  # قفل ادیت پیام
        "poll_lock": False,  # قفل نظر سنجی
        "id_in_bio_lock": False,  # قفل آیدی در بیو
        "bad_name_lock": False,  # قفل اسم نامناسب
        "bad_bio_lock": False,  # قفل بیو نامناسب
        "pv_invite_lock": False,  # قفل دعوت به پیوی
        "event_report": False,  # گزارش رویدادها
        "msg_limit": False,  # قفل تعداد پیام
        "admin_required_count": 0,  # تعداد اد اجباری
        "char_limit_count": 50,  # تعداد کاراکتر مجاز
        "welcome_media": False,  # رسانه خوش‌آمد
        "welcome_auto_delete": False,  # حذف خودکار خوش‌آمد
        "goodbye_media": False,  # رسانه خداحافظی
        "goodbye_auto_delete": False,  # حذف خودکار خداحافظی
    }

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            info("تنظیمات بارگذاری شد")
            return loaded
        except:
            error("خطا در بارگذاری تنظیمات")
            return {"groups": {}}
    else:
        default = {"groups": {}}
        save_settings(default)
        return default


def save_settings(settings_dict):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings_dict, f, ensure_ascii=False, indent=2)
    except:
        pass


def get_group_settings(chat_id):
    chat_id_str = str(chat_id)
    if "groups" not in settings:
        settings["groups"] = {}

    if chat_id_str not in settings["groups"]:
        settings["groups"][chat_id_str] = get_default_group_settings()
        save_settings(settings)

    return settings["groups"][chat_id_str]


def set_group_setting(chat_id, key, value):
    chat_id_str = str(chat_id)
    if "groups" not in settings:
        settings["groups"] = {}
    if chat_id_str not in settings["groups"]:
        settings["groups"][chat_id_str] = get_default_group_settings()

    settings["groups"][chat_id_str][key] = value
    save_settings(settings)


def get_group_setting(chat_id, key, default=None):
    group_settings = get_group_settings(chat_id)
    return group_settings.get(key, default)


settings = load_settings()
