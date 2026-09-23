# logger.py
from datetime import datetime
import os
# غیرفعال کردن کامل نوشتن در فایل
import sys
sys.stdout = sys.stderr  # یا هر کاری

# ⭐ مسیر فولدر ربات
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ⭐ فولدر data
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

LOG_FILE = os.path.join(DATA_DIR, "bot_log.txt")
LOG_FILE_FULL = os.path.join(DATA_DIR, "bot_log_full.txt")


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    MAGENTA = '\033[35m'


def log(message, level="INFO", print_to_console=True):
    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{time_str}] [{level}] {message}\n"

    # ⭐ ذخیره در فایل غیرفعال شد
    # try:
    #     with open(LOG_FILE, "a", encoding="utf-8") as f:
    #         f.write(log_message)
    # except:
    #     pass

    # try:
    #     with open(LOG_FILE_FULL, "a", encoding="utf-8") as f:
    #         f.write(log_message)
    # except:
    #     pass

    if print_to_console:
        color = {
            "INFO": Colors.CYAN,
            "SUCCESS": Colors.GREEN,
            "WARNING": Colors.YELLOW,
            "ERROR": Colors.RED,
            "DEBUG": Colors.BLUE,
            "START": Colors.HEADER,
            "BOT_SEND": Colors.MAGENTA,
        }.get(level, Colors.ENDC)

        print(f"{color}{log_message.strip()}{Colors.ENDC}")


def info(message):
    log(message, "INFO")


def success(message):
    log(message, "SUCCESS")


def warning(message):
    log(message, "WARNING")


def error(message):
    log(message, "ERROR")


def debug(message):
    log(message, "DEBUG")


def start_log():
    log("=" * 60, "START")
    log("🚀 ربات شروع به کار کرد", "START")
    log(f"📅 تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "START")
    log("=" * 60, "START")


def user_action(user_id, username, action, chat_id=None, chat_name=None):
    user_info = f"کاربر {user_id}"
    if username:
        user_info = f"{username} ({user_id})"
    location = ""
    if chat_id:
        location = f" در {chat_name or chat_id}"
    log(f"👤 {user_info} | {action}{location}", "INFO")


def admin_action(admin_id, action, target_id=None):
    msg = f"👑 ادمین {admin_id} | {action}"
    if target_id:
        msg += f" | هدف: {target_id}"
    log(msg, "WARNING")


def group_event(chat_id, chat_name, event):
    log(f"👥 گروه {chat_name} ({chat_id}) | {event}", "SUCCESS")


def error_log(where, exception):
    log(f"❌ خطا در {where}: {str(exception)}", "ERROR")


def log_bot_response(chat_id, message):
    """لاگ کردن پاسخ‌های بات"""
    msg_preview = str(message)[:200].replace("\n", " ")
    log(f"🤖 [بات] → {chat_id}: {msg_preview}", "BOT_SEND")
