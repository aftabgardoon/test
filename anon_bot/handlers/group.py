# handlers/group.py
"""
هندلر گروه - فقط برای پاسخ و ویرایش پیام ناشناس
"""

groups_count = {}
channels_count = {}


def register_group(chat_id, title=""):
    groups_count[chat_id] = {"title": title, "count": 0}


def register_channel(chat_id, title=""):
    channels_count[chat_id] = {"title": title, "count": 0}


def sync_all_groups():
    return 0


def check_members():
    pass


def check_bot_added_to_group(update):
    pass


def handle_group(chat_id, user_id, text, message_id, msg=None):
    """فقط پاسخ و ویرایش پیام ناشناس از گروه"""
    from state import reply_waiting
    from handlers.anonymous_link import handle_anonymous_reply_message, handle_anonymous_edit_message

    if user_id in reply_waiting and reply_waiting[user_id].get("type") == "alink_reply":
        if handle_anonymous_reply_message(chat_id, user_id, text, msg):
            return

    if user_id in reply_waiting and reply_waiting[user_id].get("type") == "alink_edit":
        if handle_anonymous_edit_message(chat_id, user_id, text, msg):
            return
