# handlers/private_waiting.py
"""
مدیریت waiting state ها - نسخه حداقلی برای لینک ناشناس
"""

note_waiting = {}
code_waiting = {}
support_waiting = {}
feedback_waiting = {}
anonymous_waiting = {}
ticket_waiting = {}
donate_amount = {}
donate_target = {}


def reset_all_states(user_id, chat_id=None):
    from state import reply_waiting
    if user_id in reply_waiting:
        del reply_waiting[user_id]
