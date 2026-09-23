# handlers/private_menus.py
"""
منوهای ساده - فقط لینک ناشناس
"""
from helpers import api_call, send_permanent
from config import BASE_URL
import requests


def send_main_keyboard(chat_id):
    """ارسال منوی اصلی به صورت کیبورد"""
    keyboard = {
        "keyboard": [
            ["🔗 لینک ناشناس"],
        ],
        "resize_keyboard": True,
        "persistent": True
    }
    api_call("sendMessage", json_data={
        "chat_id": chat_id,
        "text": "📱 منوی اصلی\nاز دکمه‌های زیر استفاده کن:",
        "reply_markup": keyboard
    })


def send_inline_menu(chat_id, text, buttons, reply_to=None):
    keyboard = {"inline_keyboard": buttons}
    data = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": keyboard
    }
    if reply_to:
        data["reply_to_message_id"] = reply_to
    return api_call("sendMessage", json_data=data)


def edit_inline_menu(chat_id, message_id, text, buttons):
    keyboard = {"inline_keyboard": buttons}
    try:
        requests.post(f"{BASE_URL}editMessageText", json={
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "reply_markup": keyboard
        }, timeout=10)
    except:
        pass


def delete_message(chat_id, message_id):
    try:
        requests.post(f"{BASE_URL}deleteMessage", json={
            "chat_id": chat_id,
            "message_id": message_id
        }, timeout=5)
    except:
        pass


# ⭐ دیکشنری نگهداری منوی قبلی
_last_menu = {}
_last_menu_name = {}


def set_last_menu(user_id, menu_key, menu_name=""):
    _last_menu[user_id] = menu_key
    _last_menu_name[user_id] = menu_name


def get_last_menu(user_id):
    return _last_menu.get(user_id)


def get_last_menu_name(user_id):
    return _last_menu_name.get(user_id, "🔙 بازگشت")


def clear_last_menu(user_id):
    if user_id in _last_menu:
        del _last_menu[user_id]
    if user_id in _last_menu_name:
        del _last_menu_name[user_id]
