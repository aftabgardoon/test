"""
چت ML - نسخه جایگزین (مدل اصلی موجود نیست)
chat_response مقدار None برمیگردونه تا چت به دیکشنری داخلی برگرده.
"""

_warned = False


def _warn_once():
    global _warned
    if not _warned:
        _warned = True
        try:
            from logger import warning
            warning("⚠️ مدل چت ML در دسترس نیست - از دیکشنری داخلی استفاده میشه")
        except Exception:
            pass


def chat_response(text):
    _warn_once()
    return None


def reset_conversation():
    pass
