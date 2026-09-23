"""
Gore تشخیص - نسخه جایگزین (مدل اصلی موجود نیست)
همه توابع مقدار 0.0 (سالم) برمیگردونن تا بات بدون خطا کار کنه.
"""

import os

_model = None
_warned = False


def _warn_once():
    global _warned
    if not _warned:
        _warned = True
        try:
            from logger import warning
            warning("⚠️ مدل Gore در دسترس نیست - فیلتر خشونت غیرفعال شد")
        except Exception:
            pass


def load_model():
    _warn_once()
    return None


def check_gore_score(path):
    _warn_once()
    try:
        if not path or not os.path.exists(path):
            return 0.0
    except Exception:
        pass
    return 0.0


def check_gore_score_from_path(path):
    return check_gore_score(path)
