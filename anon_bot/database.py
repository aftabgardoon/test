# database.py
import sqlite3
import os
from logger import info, error
from settings import get_group_setting

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "bot_data.db")

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()


def init_db():
    """ساخت جداول دیتابیس"""
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS force_join_pv (
            channel_id INTEGER PRIMARY KEY,
            channel_link TEXT,
            channel_title TEXT,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS force_join_pv_passed (
            user_id INTEGER PRIMARY KEY,
            passed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            points INTEGER DEFAULT 0,
            is_started INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS nsfw_settings (
            chat_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS toxic_settings (
            chat_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            note_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS warns (
            warn_key TEXT PRIMARY KEY,
            user_id INTEGER,
            chat_id INTEGER,
            count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS birthdays (
            user_id INTEGER PRIMARY KEY,
            birthday TEXT
        );

        CREATE TABLE IF NOT EXISTS shop_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item TEXT,
            price INTEGER,
            chat_id INTEGER,
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS shop_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item TEXT
        );

        CREATE TABLE IF NOT EXISTS vip_users (
            user_id INTEGER PRIMARY KEY,
            expires_at REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS special_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(chat_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS anonymous_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id INTEGER,
            message TEXT,
            chat_type TEXT,
            chat_id INTEGER,
            link_id INTEGER,
            sender_msg_id INTEGER DEFAULT 0,
            receiver_msg_id INTEGER DEFAULT 0,
            sent_msg_id INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS group_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            username TEXT,
            msg_type TEXT,
            message_id INTEGER DEFAULT 0,
            date INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            change_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS muted_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            muted_until REAL
        );

        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            member_count INTEGER DEFAULT 0,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS admin_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_admin_id INTEGER,
            to_chat_id INTEGER,
            chat_type TEXT DEFAULT 'private',
            message_text TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS support_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            reply TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS feedbacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            reply TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS force_join_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            channel_id INTEGER,
            channel_link TEXT,
            channel_title TEXT,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
         CREATE TABLE IF NOT EXISTS clean_credits (
            user_id INTEGER PRIMARY KEY,
            credits INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS force_join_passed (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            passed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(group_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS badwords_settings (
            chat_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS blocked_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blocker_id INTEGER,
            blocked_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(blocker_id, blocked_id)
        );
        CREATE TABLE IF NOT EXISTS time_tracker_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS user_credits (
            user_id INTEGER PRIMARY KEY,
            credits INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS pending_callbacks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
            callback_data TEXT,
            user_id INTEGER,
            chat_id INTEGER,
            message_id INTEGER,
            target_id INTEGER,
            callback_type TEXT,
            expires_at REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS payment_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            charge_id TEXT UNIQUE,
            user_id INTEGER,
            amount INTEGER,
            payload TEXT,
            status TEXT DEFAULT 'received',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS anonymous_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER,
            link_name TEXT,
            token TEXT UNIQUE,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS anonymous_link_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id INTEGER,
            blocked_user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(link_id, blocked_user_id)
        );
        CREATE TABLE IF NOT EXISTS user_traps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER,
            link_name TEXT DEFAULT 'تله',
            token TEXT UNIQUE,
            welcome_text TEXT DEFAULT '🪤 توی تله افتادی! 😈\n\nحالا که فهمیدم کی هستی، باید پول بدی تا لو ندمت! 💰',
            welcome_photo TEXT DEFAULT '',
            welcome_photo_caption TEXT DEFAULT '',
            welcome_media_type TEXT DEFAULT 'photo',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS trap_pending (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trap_id INTEGER,
            user_id INTEGER,
            owner_id INTEGER,
            trap_name TEXT,
            expires_at REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS trap_catches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trap_id INTEGER,
            user_id INTEGER,
            user_name TEXT,
            username TEXT DEFAULT '',
            user_photo TEXT,
            user_bio TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS group_ai_settings (
            group_id INTEGER PRIMARY KEY,
            model_key TEXT DEFAULT 'qwen-3.6',
            category_id TEXT DEFAULT 'chat',
            chatbot_enabled INTEGER DEFAULT 0
        );

        -- جدول تنظیمات ناشناس گروهی
        CREATE TABLE IF NOT EXISTS group_anonymous_settings (
            group_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0
        );

        -- جدول بن‌شده‌های ناشناس گروهی
        CREATE TABLE IF NOT EXISTS group_anonymous_bans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            banned_by INTEGER,
            message_preview TEXT,
            full_message TEXT,
            banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(group_id, user_id)
        );

        -- جدول کش فایل‌های فوروارد شده (با ریست بات پاک میشه)
        CREATE TABLE IF NOT EXISTS forwarded_media_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_unique_id TEXT UNIQUE,
            file_id TEXT,
            message_id INTEGER,
            chat_id INTEGER,
            forwarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- جدول پیام‌های ناشناس گروهی
        CREATE TABLE IF NOT EXISTS group_anonymous_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            from_user_id INTEGER,
            message TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # اضافه کردن ستون chatbot_enabled به جدول موجود (اگر وجود نداشته باشد)
    try:
        cursor.execute("ALTER TABLE group_ai_settings ADD COLUMN chatbot_enabled INTEGER DEFAULT 0")
    except:
        pass  # ستون از قبل وجود دارد

    # ⭐ جداول صندلی داغ
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hot_seat_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER,
            link_name TEXT,
            token TEXT UNIQUE,
            is_active INTEGER DEFAULT 1,
            channel_id INTEGER DEFAULT 0,
            channel_title TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hot_seat_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id INTEGER,
            from_user_id INTEGER,
            question_text TEXT,
            question_media TEXT,
            question_media_type TEXT DEFAULT 'text',
            answer_text TEXT,
            answer_media TEXT,
            answer_media_type TEXT DEFAULT 'text',
            channel_msg_id INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            dislikes INTEGER DEFAULT 0,
            is_answered INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            answered_at TIMESTAMP
        )
    """)

    # جدول بلاکی صندلی داغ
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hot_seat_link_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id INTEGER NOT NULL,
            blocked_user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(link_id, blocked_user_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hot_seat_reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER,
            user_id INTEGER,
            reaction_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(question_id, user_id)
        )
    """)

    # جدول اقدامات روی پیام‌های ناشناس و صندلی داغ
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS message_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            question_id INTEGER,
            link_id INTEGER,
            user_id INTEGER,
            action_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(message_id, user_id, action_type)
        )
    """)

    conn.commit()
    info("📂 دیتابیس SQLite با جداول جدید راه‌اندازی شد")

def add_clean_credits(user_id, amount=20):
    """اضافه کردن اعتبار پاکسازی"""
    user_id = int(user_id)
    amount = int(amount)
    cursor.execute("""
        INSERT INTO clean_credits (user_id, credits) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET credits = credits + ?
    """, (user_id, amount, amount))
    conn.commit()
    return True


def get_clean_credits(user_id):
    """گرفتن اعتبار پاکسازی باقی‌مانده"""
    cursor.execute("SELECT credits FROM clean_credits WHERE user_id = ?", (int(user_id),))
    row = cursor.fetchone()
    return row[0] if row else 0


def use_clean_credit(user_id, amount=1):
    """کم کردن اعتبار پاکسازی"""
    user_id = int(user_id)
    amount = int(amount)
    cursor.execute("UPDATE clean_credits SET credits = MAX(0, credits - ?) WHERE user_id = ?",
                   (amount, user_id))
    conn.commit()
    return get_clean_credits(user_id)

def migrate_database():
    """آپدیت ساختار دیتابیس"""
    # ⭐ اضافه کردن ستون chat_mode به user_ai_settings
    try:
        cursor.execute("SELECT chat_mode FROM user_ai_settings LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE user_ai_settings ADD COLUMN chat_mode INTEGER DEFAULT 0")
            conn.commit()
            info("✅ ستون chat_mode اضافه شد")
        except:
            pass

    try:
        cursor.execute("SELECT expires_at FROM vip_users LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE vip_users ADD COLUMN expires_at REAL DEFAULT 0")
            conn.commit()
            info("✅ ستون expires_at اضافه شد")
        except:
            pass

    try:
        cursor.execute("SELECT 1 FROM special_users LIMIT 1")
    except:
        try:
            cursor.execute("""CREATE TABLE IF NOT EXISTS special_users (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, user_id INTEGER, added_by INTEGER, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(chat_id, user_id))""")
            conn.commit()
            info("✅ جدول special_users ساخته شد")
        except:
            pass

    try:
        cursor.execute("SELECT 1 FROM force_join_pv LIMIT 1")
    except:
        try:
            cursor.execute("""CREATE TABLE IF NOT EXISTS force_join_pv (channel_id INTEGER PRIMARY KEY, channel_link TEXT, channel_title TEXT, added_by INTEGER, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            conn.commit()
        except: pass

    try:
        cursor.execute("SELECT 1 FROM force_join_pv_passed LIMIT 1")
    except:
        try:
            cursor.execute("""CREATE TABLE IF NOT EXISTS force_join_pv_passed (user_id INTEGER PRIMARY KEY, passed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            conn.commit()
        except: pass

    try:
        cursor.execute("SELECT sent_msg_id FROM anonymous_messages LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE anonymous_messages ADD COLUMN sent_msg_id INTEGER DEFAULT 0")
            conn.commit()
            info("✅ ستون sent_msg_id اضافه شد")
        except:
            pass

    # ⭐ اضافه کردن display_name به users
    try:
        cursor.execute("SELECT display_name FROM users LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN display_name TEXT")
            conn.commit()
            info("✅ ستون display_name اضافه شد")
        except:
            pass

    # ⭐ اضافه کردن link_id به anonymous_messages
    try:
        cursor.execute("SELECT link_id FROM anonymous_messages LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE anonymous_messages ADD COLUMN link_id INTEGER")
            conn.commit()
            info("✅ ستون link_id اضافه شد")
        except:
            pass

    # ⭐ اضافه کردن group_title به anonymous_links
    try:
        cursor.execute("SELECT group_title FROM anonymous_links LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE anonymous_links ADD COLUMN group_title TEXT")
            conn.commit()
            info("✅ ستون group_title به anonymous_links اضافه شد")
        except:
            pass

    # ⭐ اضافه کردن channel_id و channel_title به anonymous_links
    try:
        cursor.execute("SELECT channel_id FROM anonymous_links LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE anonymous_links ADD COLUMN channel_id INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE anonymous_links ADD COLUMN channel_title TEXT DEFAULT ''")
            conn.commit()
            info("✅ ستون‌های channel_id و channel_title اضافه شد")
        except:
            pass

    # ⭐ اضافه کردن تنظیمات امنیتی برای هر لینک
    try:
        cursor.execute("SELECT anti_nsfw FROM anonymous_links LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE anonymous_links ADD COLUMN anti_nsfw INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE anonymous_links ADD COLUMN anti_badwords INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE anonymous_links ADD COLUMN anti_gore INTEGER DEFAULT 0")
            conn.commit()
            info("✅ ستون‌های anti_nsfw, anti_badwords, anti_gore اضافه شد")
        except:
            pass
    # ⭐ اضافه کردن ستون‌های جدید به user_traps
    try:
        cursor.execute("SELECT welcome_photo_caption FROM user_traps LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE user_traps ADD COLUMN welcome_photo_caption TEXT DEFAULT ''")
            conn.commit()
            info("✅ ستون welcome_photo_caption اضافه شد")
        except:
            pass

    try:
        cursor.execute("SELECT link_name FROM user_traps LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE user_traps ADD COLUMN link_name TEXT DEFAULT 'تله'")
            conn.commit()
            info("✅ ستون link_name اضافه شد")
        except:
            pass

    try:
        cursor.execute("SELECT is_active FROM user_traps LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE user_traps ADD COLUMN is_active INTEGER DEFAULT 1")
            conn.commit()
            info("✅ ستون is_active اضافه شد")
        except:
            pass

    try:
        cursor.execute("SELECT hidden_text FROM user_traps LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE user_traps ADD COLUMN hidden_text TEXT DEFAULT ''")
            conn.commit()
            info("✅ ستون hidden_text اضافه شد")
        except:
            pass

    try:
        cursor.execute("SELECT username FROM trap_catches LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE trap_catches ADD COLUMN username TEXT DEFAULT ''")
            conn.commit()
            info("✅ ستون username به trap_catches اضافه شد")
        except:
            pass

    # ⭐ اضافه کردن ستون‌های تنظیمات مدیا به anonymous_links
    try:
        cursor.execute("SELECT anti_media FROM anonymous_links LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE anonymous_links ADD COLUMN anti_media INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE anonymous_links ADD COLUMN anti_photo INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE anonymous_links ADD COLUMN anti_video INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE anonymous_links ADD COLUMN anti_audio INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE anonymous_links ADD COLUMN anti_document INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE anonymous_links ADD COLUMN anti_sticker INTEGER DEFAULT 0")
            conn.commit()
            info("✅ ستون‌های تنظیمات مدیا به anonymous_links اضافه شد")
        except:
            pass

    # ⭐ اضافه کردن ستون message_id به group_stats
    try:
        cursor.execute("SELECT message_id FROM group_stats LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE group_stats ADD COLUMN message_id INTEGER DEFAULT 0")
            conn.commit()
            info("✅ ستون message_id به group_stats اضافه شد")
        except:
            pass

    try:
        cursor.execute("SELECT welcome_media_type FROM user_traps LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE user_traps ADD COLUMN welcome_media_type TEXT DEFAULT 'photo'")
            conn.commit()
            info("✅ ستون welcome_media_type اضافه شد")
        except:
            pass
    # ⭐ اضافه کردن ستون file_id به group_stats
    try:
        cursor.execute("SELECT file_id FROM group_stats LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE group_stats ADD COLUMN file_id TEXT DEFAULT ''")
            conn.commit()
            info("✅ ستون file_id به group_stats اضافه شد")
        except:
            pass

# ====== توابع کاربران ======
def add_user(user_id):
    cursor.execute("""
        INSERT INTO users (user_id, points, is_started) VALUES (?, 0, 1)
        ON CONFLICT(user_id) DO UPDATE SET is_started = 1
    """, (int(user_id),))
    conn.commit()

def get_started_users():
    cursor.execute("SELECT user_id FROM users WHERE is_started = 1")
    return set(row[0] for row in cursor.fetchall())

def get_all_users():
    cursor.execute("SELECT user_id FROM users")
    return [row[0] for row in cursor.fetchall()]

def get_points(user_id):
    cursor.execute("SELECT points FROM users WHERE user_id = ?", (int(user_id),))
    row = cursor.fetchone()
    return row[0] if row else 0

def add_points(user_id, amount=1):
    from config import WHITE_LIST
    user_id = int(user_id)
    amount = int(amount)
    if user_id in WHITE_LIST:
        return
    cursor.execute("""
        INSERT INTO users (user_id, points, is_started) VALUES (?, ?, 1)
        ON CONFLICT(user_id) DO UPDATE SET points = points + ?
    """, (user_id, amount, amount))
    conn.commit()

def remove_points(user_id, amount=1):
    from config import WHITE_LIST
    user_id = int(user_id)
    amount = int(amount)
    if user_id in WHITE_LIST:
        return

    cursor.execute("INSERT OR IGNORE INTO users (user_id, points, is_started) VALUES (?, 0, 0)", (user_id,))
    cursor.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

    cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0

# ====== توابع یادداشت ======
def add_note(user_id, note_text):
    user_id = int(user_id)
    cursor.execute("INSERT INTO notes (user_id, note_text) VALUES (?, ?)", (user_id, note_text))
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM notes WHERE user_id = ?", (user_id,))
    return cursor.fetchone()[0]

def get_notes(user_id):
    user_id = int(user_id)
    cursor.execute("SELECT note_text FROM notes WHERE user_id = ? ORDER BY id", (user_id,))
    return [row[0] for row in cursor.fetchall()]

def clear_notes(user_id):
    user_id = int(user_id)
    cursor.execute("DELETE FROM notes WHERE user_id = ?", (user_id,))
    conn.commit()
    return True

# ====== توابع اخطار ======
def set_warn(chat_id, user_id):
    chat_id = int(chat_id)
    user_id = int(user_id)
    warn_key = f"{chat_id}_{user_id}"
    cursor.execute("""
        INSERT INTO warns (warn_key, user_id, chat_id, count) VALUES (?, ?, ?, 1)
        ON CONFLICT(warn_key) DO UPDATE SET count = count + 1
    """, (warn_key, user_id, chat_id))
    conn.commit()
    cursor.execute("SELECT count FROM warns WHERE warn_key = ?", (warn_key,))
    return cursor.fetchone()[0]

def get_warns_dict():
    cursor.execute("SELECT warn_key, count FROM warns")
    return {row[0]: row[1] for row in cursor.fetchall()}

def clear_warns_for_user(user_id):
    user_id = int(user_id)
    cursor.execute("DELETE FROM warns WHERE user_id = ?", (user_id,))
    conn.commit()

def clear_warn_key(warn_key):
    cursor.execute("DELETE FROM warns WHERE warn_key = ?", (warn_key,))
    conn.commit()

# ====== توابع تولد ======
def set_birthday(user_id, birthday):
    user_id = int(user_id)
    cursor.execute("INSERT OR REPLACE INTO birthdays (user_id, birthday) VALUES (?, ?)", (user_id, birthday))
    conn.commit()


def get_birthdays():
    cursor.execute("SELECT user_id, birthday FROM birthdays")
    return {row[0]: row[1] for row in cursor.fetchall()}


# ====== توابع فروشگاه ======
def add_shop_history(user_id, item, price, chat_id):
    user_id = int(user_id)
    price = int(price)
    chat_id = int(chat_id)
    cursor.execute("INSERT INTO shop_history (user_id, item, price, chat_id) VALUES (?, ?, ?, ?)",
                   (user_id, item, price, chat_id))
    conn.commit()


def get_shop_history(user_id):
    user_id = int(user_id)
    cursor.execute("SELECT item, price FROM shop_history WHERE user_id = ? ORDER BY id DESC", (user_id,))
    return [{"item": row[0], "price": row[1]} for row in cursor.fetchall()]


# ====== توابع VIP (فروشگاهی - یک هفته) ======
def add_vip(user_id, duration_days=7):
    """اضافه کردن VIP برای مدت مشخص (پیش‌فرض ۷ روز)"""
    import time
    user_id = int(user_id)
    expires_at = time.time() + (duration_days * 86400) if duration_days > 0 else 0
    cursor.execute("INSERT OR REPLACE INTO vip_users (user_id, expires_at) VALUES (?, ?)",
                   (user_id, expires_at))
    conn.commit()
    return True


def remove_vip(user_id):
    """حذف VIP"""
    cursor.execute("DELETE FROM vip_users WHERE user_id = ?", (int(user_id),))
    conn.commit()


def get_vip_users():
    """لیست VIP های فعال (منقضی نشده)"""
    import time
    now = time.time()
    cursor.execute("SELECT user_id FROM vip_users WHERE expires_at = 0 OR expires_at > ?", (now,))
    return [row[0] for row in cursor.fetchall()]


def is_vip(user_id):
    import time
    if user_id is None:
        return False
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return False
    now = time.time()
    cursor.execute("SELECT 1 FROM vip_users WHERE user_id = ? AND (expires_at = 0 OR expires_at > ?)",
                   (user_id, now))
    return cursor.fetchone() is not None


def get_vip_expiry(user_id):
    """گرفتن تاریخ انقضای VIP"""
    cursor.execute("SELECT expires_at FROM vip_users WHERE user_id = ?", (int(user_id),))
    row = cursor.fetchone()
    if row:
        if row[0] == 0:
            return "دائم"
        import jdatetime
        from datetime import datetime
        dt = datetime.fromtimestamp(row[0])
        jalali = jdatetime.datetime.fromgregorian(datetime=dt)
        return f"{jalali.year}/{jalali.month:02d}/{jalali.day:02d}"
    return None


# ====== توابع کاربران ویژه گروهی ======
def add_special_user(chat_id, user_id, added_by):
    """اضافه کردن کاربر ویژه برای یک گروه خاص"""
    chat_id = int(chat_id)
    user_id = int(user_id)
    added_by = int(added_by)
    cursor.execute("INSERT OR IGNORE INTO special_users (chat_id, user_id, added_by) VALUES (?, ?, ?)",
                   (chat_id, user_id, added_by))
    conn.commit()
    return True


def remove_special_user(chat_id, user_id):
    """حذف کاربر ویژه از یک گروه خاص"""
    cursor.execute("DELETE FROM special_users WHERE chat_id = ? AND user_id = ?",
                   (int(chat_id), int(user_id)))
    conn.commit()
    return True


def is_special_in_group(chat_id, user_id):
    """چک کن کاربر توی این گروه ویژه هست یا نه"""
    cursor.execute("SELECT 1 FROM special_users WHERE chat_id = ? AND user_id = ?",
                   (int(chat_id), int(user_id)))
    return cursor.fetchone() is not None


def get_special_users_in_group(chat_id):
    """لیست کاربران ویژه یک گروه"""
    cursor.execute("SELECT user_id FROM special_users WHERE chat_id = ?", (int(chat_id),))
    return [row[0] for row in cursor.fetchall()]


def get_all_special_users():
    """لیست همه کاربران ویژه با گروه‌هاشون"""
    cursor.execute("SELECT chat_id, user_id FROM special_users")
    return [{"chat_id": row[0], "user_id": row[1]} for row in cursor.fetchall()]


# ====== توابع سکوت/بن ======
def add_muted_user(chat_id, user_id, until_time):
    chat_id = int(chat_id)
    user_id = int(user_id)
    cursor.execute("INSERT INTO muted_users (chat_id, user_id, muted_until) VALUES (?, ?, ?)",
                   (chat_id, user_id, until_time))
    conn.commit()


def get_muted_groups_for_user(user_id):
    import time
    user_id = int(user_id)
    cursor.execute("SELECT chat_id FROM muted_users WHERE user_id = ? AND muted_until > ?",
                   (user_id, time.time()))
    return [row[0] for row in cursor.fetchall()]

# ====== توابع آمار ======
def add_group_stat(chat_id, user_id, username, msg_type, message_id=0, file_id=""):
    # ⭐ اگه user_id نامعتبر بود، رد کن
    if user_id is None:
        return
    chat_id = int(chat_id)
    user_id = int(user_id)
    import time
    current_time = int(time.time())
    cursor.execute("""
        INSERT INTO group_stats (chat_id, user_id, username, msg_type, message_id, file_id, date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (chat_id, user_id, username, msg_type, int(message_id), file_id, current_time))
    conn.commit()

def get_group_stats(chat_id):
    chat_id = int(chat_id)
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN msg_type = 'photo' THEN 1 ELSE 0 END) as photos,
            SUM(CASE WHEN msg_type = 'video' THEN 1 ELSE 0 END) as videos,
            SUM(CASE WHEN msg_type = 'animation' THEN 1 ELSE 0 END) as animations,
            SUM(CASE WHEN msg_type = 'sticker' THEN 1 ELSE 0 END) as stickers,
            SUM(CASE WHEN msg_type = 'voice' THEN 1 ELSE 0 END) as voices,
            SUM(CASE WHEN msg_type = 'audio' THEN 1 ELSE 0 END) as audios,
            SUM(CASE WHEN msg_type = 'document' THEN 1 ELSE 0 END) as files,
            SUM(CASE WHEN msg_type = 'contact' THEN 1 ELSE 0 END) as contacts,
            SUM(CASE WHEN msg_type = 'location' THEN 1 ELSE 0 END) as locations
        FROM group_stats WHERE chat_id = ?
    """, (chat_id,))
    row = cursor.fetchone()

    cursor.execute("""
        SELECT user_id, username, COUNT(*) as cnt
        FROM group_stats
        WHERE chat_id = ? AND username IS NOT NULL AND username != ''
        GROUP BY user_id
        ORDER BY cnt DESC
        LIMIT 10
    """, (chat_id,))
    top_users = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM group_members WHERE chat_id = ? AND change_type = 'join'", (chat_id,))
    joins = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM group_members WHERE chat_id = ? AND change_type = 'leave'", (chat_id,))
    leaves = cursor.fetchone()[0]

    return {
        "total": row[0] or 0,
        "photos": row[1] or 0,
        "videos": row[2] or 0,
        "animations": row[3] or 0,
        "stickers": row[4] or 0,
        "voices": row[5] or 0,
        "audios": row[6] or 0,
        "files": row[7] or 0,
        "contacts": row[8] or 0,
        "locations": row[9] or 0,
        "joins": joins,
        "leaves": leaves,
        "top_users": top_users
    }

def get_group_stats_by_period(chat_id, start_time, end_time):
    """دریافت آمار گروه در بازه زمانی مشخص"""
    chat_id = int(chat_id)
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN msg_type = 'photo' THEN 1 ELSE 0 END) as photos,
            SUM(CASE WHEN msg_type = 'video' THEN 1 ELSE 0 END) as videos,
            SUM(CASE WHEN msg_type = 'animation' THEN 1 ELSE 0 END) as animations,
            SUM(CASE WHEN msg_type = 'sticker' THEN 1 ELSE 0 END) as stickers,
            SUM(CASE WHEN msg_type = 'voice' THEN 1 ELSE 0 END) as voices,
            SUM(CASE WHEN msg_type = 'audio' THEN 1 ELSE 0 END) as audios,
            SUM(CASE WHEN msg_type = 'document' THEN 1 ELSE 0 END) as files,
            SUM(CASE WHEN msg_type = 'contact' THEN 1 ELSE 0 END) as contacts,
            SUM(CASE WHEN msg_type = 'location' THEN 1 ELSE 0 END) as locations
        FROM group_stats
        WHERE chat_id = ? AND date BETWEEN ? AND ?
    """, (chat_id, start_time, end_time))
    row = cursor.fetchone()

    cursor.execute("""
        SELECT user_id, username, COUNT(*) as cnt
        FROM group_stats
        WHERE chat_id = ? AND date BETWEEN ? AND ?
            AND username IS NOT NULL AND username != ''
        GROUP BY user_id
        ORDER BY cnt DESC
        LIMIT 5
    """, (chat_id, start_time, end_time))
    top_users = cursor.fetchall()

    return {
        "total": row[0] or 0,
        "photos": row[1] or 0,
        "videos": row[2] or 0,
        "animations": row[3] or 0,
        "stickers": row[4] or 0,
        "voices": row[5] or 0,
        "audios": row[6] or 0,
        "files": row[7] or 0,
        "contacts": row[8] or 0,
        "locations": row[9] or 0,
        "top_users": top_users
    }

def get_group_total_stats(chat_id):
    """دریافت آمار کل گروه (همیشه)"""
    return get_group_stats(chat_id)

def add_member_change(chat_id, change_type):
    chat_id = int(chat_id)
    cursor.execute("INSERT INTO group_members (chat_id, change_type) VALUES (?, ?)", (chat_id, change_type))
    conn.commit()


# ====== توابع گروه‌ها ======
def save_group(chat_id, title="گروه", member_count=0):
    chat_id = int(chat_id)
    cursor.execute("""
        INSERT INTO groups (chat_id, title, member_count) VALUES (?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            title = excluded.title,
            member_count = excluded.member_count,
            updated_at = CURRENT_TIMESTAMP
    """, (chat_id, title, member_count))
    conn.commit()
    return True


def get_all_groups():
    cursor.execute("SELECT chat_id, title, member_count FROM groups ORDER BY member_count DESC")
    return [{"chat_id": row[0], "title": row[1], "member_count": row[2]} for row in cursor.fetchall()]


def get_group_count():
    cursor.execute("SELECT COUNT(*) FROM groups")
    return cursor.fetchone()[0]


def update_group_member_count(chat_id, count):
    chat_id = int(chat_id)
    count = int(count)
    cursor.execute("UPDATE groups SET member_count = ?, updated_at = CURRENT_TIMESTAMP WHERE chat_id = ?", (count, chat_id))
    conn.commit()


# ====== توابع پیام‌های ادمین ======
def save_admin_message(admin_id, to_chat_id, message_text, chat_type="private"):
    admin_id = int(admin_id)
    to_chat_id = int(to_chat_id)
    cursor.execute("""
        INSERT INTO admin_messages (from_admin_id, to_chat_id, chat_type, message_text)
        VALUES (?, ?, ?, ?)
    """, (admin_id, to_chat_id, chat_type, message_text))
    conn.commit()
    return cursor.lastrowid


def get_admin_messages(admin_id=None, limit=50):
    if admin_id:
        cursor.execute("""
            SELECT from_admin_id, to_chat_id, chat_type, message_text, sent_at
            FROM admin_messages WHERE from_admin_id = ?
            ORDER BY id DESC LIMIT ?
        """, (int(admin_id), limit))
    else:
        cursor.execute("""
            SELECT from_admin_id, to_chat_id, chat_type, message_text, sent_at
            FROM admin_messages
            ORDER BY id DESC LIMIT ?
        """, (limit,))
    return cursor.fetchall()


# ====== توابع پشتیبانی ======
def save_support_message(user_id, message):
    cursor.execute("INSERT INTO support_chats (user_id, message) VALUES (?, ?)", (int(user_id), message))
    conn.commit()
    return cursor.lastrowid


def save_support_reply(chat_id, reply_text):
    cursor.execute("UPDATE support_chats SET reply = ?, status = 'replied' WHERE id = ?", (reply_text, int(chat_id)))
    conn.commit()


def get_open_support_chats():
    cursor.execute("SELECT id, user_id, message, created_at FROM support_chats WHERE status = 'open' ORDER BY id DESC LIMIT 20")
    return cursor.fetchall()


def get_all_support_chats(limit=30):
    cursor.execute("SELECT id, user_id, message, reply, status, created_at FROM support_chats ORDER BY id DESC LIMIT ?", (limit,))
    return cursor.fetchall()


def get_support_chat(chat_id):
    cursor.execute("SELECT id, user_id, message, reply, status FROM support_chats WHERE id = ?", (int(chat_id),))
    return cursor.fetchone()


def get_user_support_chats(user_id, limit=10):
    cursor.execute("SELECT id, message, reply, status, created_at FROM support_chats WHERE user_id = ? ORDER BY id DESC LIMIT ?", (int(user_id), limit))
    return cursor.fetchall()


# ====== توابع انتقادات ======
def save_feedback(user_id, message):
    cursor.execute("INSERT INTO feedbacks (user_id, message) VALUES (?, ?)", (int(user_id), message))
    conn.commit()
    return cursor.lastrowid


def save_feedback_reply(feedback_id, reply_text):
    cursor.execute("UPDATE feedbacks SET reply = ?, status = 'replied' WHERE id = ?", (reply_text, int(feedback_id)))
    conn.commit()


def get_open_feedbacks():
    cursor.execute("SELECT id, user_id, message, created_at FROM feedbacks WHERE status = 'open' ORDER BY id DESC LIMIT 20")
    return cursor.fetchall()


def get_all_feedbacks(limit=30):
    cursor.execute("SELECT id, user_id, message, reply, status, created_at FROM feedbacks ORDER BY id DESC LIMIT ?", (limit,))
    return cursor.fetchall()


def get_feedback(feedback_id):
    cursor.execute("SELECT id, user_id, message, reply, status FROM feedbacks WHERE id = ?", (int(feedback_id),))
    return cursor.fetchone()


# ====== توابع عضویت اجباری ======
def add_force_join_channel(group_id, channel_id, channel_link, channel_title, added_by):
    """اضافه کردن کانال/گروه به لیست عضویت اجباری"""
    cursor.execute("""
        INSERT OR IGNORE INTO force_join_channels (group_id, channel_id, channel_link, channel_title, added_by)
        VALUES (?, ?, ?, ?, ?)
    """, (int(group_id), int(channel_id), channel_link, channel_title, int(added_by)))
    conn.commit()
    return True


def remove_force_join_channel(group_id, channel_id):
    """حذف کانال/گروه از لیست عضویت اجباری"""
    cursor.execute("DELETE FROM force_join_channels WHERE group_id = ? AND channel_id = ?",
                   (int(group_id), int(channel_id)))
    conn.commit()
    return True


def get_force_join_channels(group_id):
    """دریافت لیست کانال‌های عضویت اجباری یک گروه"""
    cursor.execute("""
        SELECT channel_id, channel_link, channel_title FROM force_join_channels
        WHERE group_id = ?
    """, (int(group_id),))
    return [{"channel_id": row[0], "channel_link": row[1], "channel_title": row[2]} for row in cursor.fetchall()]


def clear_force_join_channels(group_id):
    """حذف همه کانال‌های عضویت اجباری یک گروه"""
    cursor.execute("DELETE FROM force_join_channels WHERE group_id = ?", (int(group_id),))
    conn.commit()
    return True


def mark_user_passed_force_join(group_id, user_id):
    """علامت‌گذاری کاربر به عنوان تأیید شده در عضویت اجباری"""
    cursor.execute("""
        INSERT OR IGNORE INTO force_join_passed (group_id, user_id) VALUES (?, ?)
    """, (int(group_id), int(user_id)))
    conn.commit()
    return True


def has_user_passed_force_join(group_id, user_id):
    """چک کردن اینکه کاربر قبلاً تأیید شده یا نه"""
    cursor.execute("""
        SELECT 1 FROM force_join_passed WHERE group_id = ? AND user_id = ?
    """, (int(group_id), int(user_id)))
    return cursor.fetchone() is not None


def clear_force_join_passed(group_id=None, user_id=None):
    """پاک کردن تأییدیه‌ها"""
    if group_id and user_id:
        cursor.execute("DELETE FROM force_join_passed WHERE group_id = ? AND user_id = ?",
                       (int(group_id), int(user_id)))
    elif group_id:
        cursor.execute("DELETE FROM force_join_passed WHERE group_id = ?", (int(group_id),))
    else:
        cursor.execute("DELETE FROM force_join_passed")
    conn.commit()
    return True


def block_user(blocker_id, blocked_id):
    """بلاک کردن یه کاربر"""
    cursor.execute("INSERT OR IGNORE INTO blocked_users (blocker_id, blocked_id) VALUES (?, ?)",
                   (int(blocker_id), int(blocked_id)))
    conn.commit()
    return True

def unblock_user(blocker_id, blocked_id):
    """درآوردن از بلاکی"""
    cursor.execute("DELETE FROM blocked_users WHERE blocker_id=? AND blocked_id=?",
                   (int(blocker_id), int(blocked_id)))
    # ⭐ بلاک‌های لینکی رو هم پاک کن
    cursor.execute("DELETE FROM anonymous_link_blocks WHERE blocked_user_id=? AND link_id IN (SELECT id FROM anonymous_links WHERE owner_id=?)",
                   (int(blocked_id), int(blocker_id)))
    conn.commit()
    return True

def get_blocked_users(blocker_id):
    """لیست کاربران بلاک‌شده"""
    cursor.execute("SELECT blocked_id FROM blocked_users WHERE blocker_id=?", (int(blocker_id),))
    return [row[0] for row in cursor.fetchall()]

def is_user_blocked(blocker_id, blocked_id):
    """چک کن کاربر بلاک شده یا نه"""
    cursor.execute("SELECT 1 FROM blocked_users WHERE blocker_id=? AND blocked_id=?",
                   (int(blocker_id), int(blocked_id)))
    return cursor.fetchone() is not None

def set_nsfw_enabled(chat_id, enabled=True):
    cursor.execute(
        "INSERT OR REPLACE INTO nsfw_settings (chat_id, enabled) VALUES (?, ?)",
        (int(chat_id), 1 if enabled else 0)
    )
    conn.commit()

def set_badwords_enabled(chat_id, enabled=True):
    cursor.execute(
        "INSERT OR REPLACE INTO badwords_settings (chat_id, enabled) VALUES (?, ?)",
        (int(chat_id), 1 if enabled else 0)
    )
    conn.commit()

def is_badwords_enabled(chat_id):
    cur = conn.cursor()
    cur.execute("SELECT enabled FROM badwords_settings WHERE chat_id = ?", (int(chat_id),))
    row = cur.fetchone()
    cur.close()
    return row[0] == 1 if row else False

def is_nsfw_enabled(chat_id):
    cur = conn.cursor()
    cur.execute("SELECT enabled FROM nsfw_settings WHERE chat_id = ?", (int(chat_id),))
    row = cur.fetchone()
    cur.close()
    return row[0] == 1 if row else False

def set_toxic_enabled(chat_id, enabled=True):
    cursor.execute(
        "INSERT OR REPLACE INTO toxic_settings (chat_id, enabled) VALUES (?, ?)",
        (int(chat_id), 1 if enabled else 0)
    )
    conn.commit()

def is_toxic_enabled(chat_id):
    cur = conn.cursor()
    cur.execute("SELECT enabled FROM toxic_settings WHERE chat_id = ?", (int(chat_id),))
    row = cur.fetchone()
    cur.close()
    return row[0] == 1 if row else False


def save_last_update_id(update_id):
    """ذخیره آخرین update_id"""
    import time
    for _ in range(3):
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO time_tracker_settings (key, value) VALUES ('last_update_id', ?)
            """, (str(update_id),))
            conn.commit()
            return
        except:
            time.sleep(0.5)

def get_last_update_id():
    """دریافت آخرین update_id"""
    cursor.execute("SELECT value FROM time_tracker_settings WHERE key='last_update_id'")
    row = cursor.fetchone()
    return int(row[0]) if row else 0

def is_test_nsfw_enabled(chat_id):
    cur = conn.cursor()
    cur.execute("SELECT value FROM time_tracker_settings WHERE key=?", (f"test_nsfw_{chat_id}",))
    row = cur.fetchone()
    cur.close()
    return row[0] == 'True' if row else False

def set_test_nsfw_enabled(chat_id, enabled=True):
    cursor.execute(
        "INSERT OR REPLACE INTO time_tracker_settings (key, value) VALUES (?, ?)",
        (f"test_nsfw_{chat_id}", str(enabled))
    )
    conn.commit()

# ====== توابع عضویت اجباری پیوی ======
def add_force_join_pv(channel_id, channel_link, channel_title, added_by):
    """اضافه کردن کانال به لیست عضویت اجباری پیوی"""
    cursor.execute("INSERT OR REPLACE INTO force_join_pv (channel_id, channel_link, channel_title, added_by) VALUES (?, ?, ?, ?)",
                   (int(channel_id), channel_link, channel_title, int(added_by)))
    conn.commit()
    return True

def remove_force_join_pv(channel_id):
    """حذف کانال از لیست عضویت اجباری پیوی"""
    cursor.execute("DELETE FROM force_join_pv WHERE channel_id = ?", (int(channel_id),))
    conn.commit()
    return True

def get_force_join_pv_channels():
    """دریافت لیست کانال‌های عضویت اجباری پیوی"""
    cursor.execute("SELECT channel_id, channel_link, channel_title FROM force_join_pv")
    return [{"channel_id": row[0], "channel_link": row[1], "channel_title": row[2]} for row in cursor.fetchall()]

def clear_force_join_pv():
    """حذف همه کانال‌های عضویت اجباری پیوی"""
    cursor.execute("DELETE FROM force_join_pv")
    conn.commit()
    return True

def mark_user_passed_force_join_pv(user_id):
    """علامت‌گذاری کاربر به عنوان تأیید شده"""
    cursor.execute("INSERT OR REPLACE INTO force_join_pv_passed (user_id) VALUES (?)", (int(user_id),))
    conn.commit()
    return True

def has_user_passed_force_join_pv(user_id):
    """چک کردن تأیید کاربر"""
    cursor.execute("SELECT 1 FROM force_join_pv_passed WHERE user_id = ?", (int(user_id),))
    return cursor.fetchone() is not None

def reset_force_join_pv_passed():
    """ریست کردن تأییدیه‌ها"""
    cursor.execute("DELETE FROM force_join_pv_passed")
    conn.commit()
    return True

# ====== توابع عضویت اجباری پیوی ======

def is_force_join_pv_enabled():
    """چک کن آیا عضویت اجباری پیوی فعاله یا نه"""
    cursor.execute("SELECT COUNT(*) FROM force_join_pv")
    return cursor.fetchone()[0] > 0

def get_user_credit(user_id):
    """گرفتن اعتبار کاربر"""
    cursor.execute("SELECT credits FROM user_credits WHERE user_id = ?", (int(user_id),))
    row = cursor.fetchone()
    return row[0] if row else 0

def add_user_credit(user_id, amount):
    """اضافه کردن اعتبار به ریال"""
    cursor.execute("""
        INSERT INTO user_credits (user_id, credits) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET credits = credits + ?
    """, (int(user_id), amount, amount))
    conn.commit()

def deduct_user_credit(user_id, amount):
    """کم کردن اعتبار کاربر"""
    cursor.execute("UPDATE user_credits SET credits = credits - ? WHERE user_id = ?",
                   (amount, int(user_id)))
    conn.commit()
    return get_user_credit(user_id)

def is_started(user_id):
    """چک کن کاربر ربات رو استارت کرده یا نه"""
    cursor.execute("SELECT is_started FROM users WHERE user_id = ?", (int(user_id),))
    row = cursor.fetchone()
    return row and row[0] == 1

def save_callback_state(callback_data, user_id, chat_id, message_id, target_id, callback_type, expire_hours=48):
    """ذخیره وضعیت دکمه در دیتابیس"""
    import time
    expires_at = time.time() + (expire_hours * 3600)
    cursor.execute("""
        INSERT INTO pending_callbacks (callback_data, user_id, chat_id, message_id, target_id, callback_type, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (callback_data, user_id, chat_id, message_id, target_id, callback_type, expires_at))
    conn.commit()
    return cursor.lastrowid

def is_callback_valid(callback_data, user_id):
    """چک کن دکمه هنوز معتبر هست یا نه"""
    import time
    cursor.execute("""
        SELECT id, expires_at FROM pending_callbacks
        WHERE callback_data = ? AND user_id = ? AND expires_at > ?
    """, (callback_data, user_id, time.time()))
    row = cursor.fetchone()
    if row:
        # حذف بعد از استفاده (یکبار مصرف)
        cursor.execute("DELETE FROM pending_callbacks WHERE id = ?", (row[0],))
        conn.commit()
        return True
    return False

def reset_force_join_pv_passed_for_user(user_id):
    """پاک کردن تایید عضویت یک کاربر خاص"""
    cursor.execute("DELETE FROM force_join_pv_passed WHERE user_id = ?", (int(user_id),))
    conn.commit()
    return True

# ====== توابع لینک ناشناس ======
def create_anonymous_link(owner_id, link_name):
    """ساخت لینک ناشناس جدید"""
    import hashlib, time
    token = hashlib.md5(f"{owner_id}_{link_name}_{time.time()}".encode()).hexdigest()[:12]
    cursor.execute(
        "INSERT INTO anonymous_links (owner_id, link_name, token) VALUES (?, ?, ?)",
        (int(owner_id), link_name, token)
    )
    conn.commit()
    return token

def get_user_anonymous_links(owner_id):
    """دریافت لیست لینک‌های ناشناس یک کاربر"""
    cursor.execute(
        "SELECT id, link_name, token, is_active, COALESCE(group_id, 0) as group_id, COALESCE(group_title, '') as group_title, COALESCE(channel_id, 0) as channel_id, COALESCE(channel_title, '') as channel_title FROM anonymous_links WHERE owner_id = ? ORDER BY id",
        (int(owner_id),)
    )
    return [{"id": row[0], "link_name": row[1], "token": row[2], "is_active": row[3], "group_id": row[4], "group_title": row[5], "channel_id": row[6], "channel_title": row[7]} for row in cursor.fetchall()]

def deactivate_anonymous_link(link_id, owner_id):
    """منسوخ کردن یه لینک"""
    cursor.execute(
        "UPDATE anonymous_links SET is_active = 0 WHERE id = ? AND owner_id = ?",
        (int(link_id), int(owner_id))
    )
    conn.commit()
    return cursor.rowcount > 0

def get_anonymous_link_by_token(token):
    """پیدا کردن لینک با توکن"""
    cursor.execute(
        "SELECT id, owner_id, link_name, is_active FROM anonymous_links WHERE token = ?",
        (token,)
    )
    row = cursor.fetchone()
    if row:
        return {"id": row[0], "owner_id": row[1], "link_name": row[2], "is_active": row[3]}
    return None

def get_user_display_name(user_id):
    """دریافت نام نمایشی کاربر"""
    cursor.execute("SELECT display_name FROM users WHERE user_id = ?", (int(user_id),))
    row = cursor.fetchone()
    return row[0] if row and row[0] else None

def set_user_display_name(user_id, display_name):
    """تنظیم نام نمایشی کاربر"""
    cursor.execute(
        "UPDATE users SET display_name = ? WHERE user_id = ?",
        (display_name, int(user_id))
    )
    if cursor.rowcount == 0:
        cursor.execute(
            "INSERT INTO users (user_id, display_name, points, is_started) VALUES (?, ?, 0, 0)",
            (int(user_id), display_name)
        )
    conn.commit()

def regenerate_anonymous_token(link_id, owner_id):
    """تولید توکن جدید برای لینک (لینک قبلی منسوخ میشه)"""
    import hashlib, time
    new_token = hashlib.md5(f"{owner_id}_{link_id}_{time.time()}".encode()).hexdigest()[:12]
    cursor.execute(
        "UPDATE anonymous_links SET token = ?, is_active = 1 WHERE id = ? AND owner_id = ?",
        (new_token, int(link_id), int(owner_id))
    )
    conn.commit()
    return new_token if cursor.rowcount > 0 else None

def set_anonymous_link_group(link_id, owner_id, group_id, group_title=""):
    """تنظیم گروه برای یه لینک ناشناس (0 یعنی پیوی)"""
    cursor.execute(
        "UPDATE anonymous_links SET group_id = ?, group_title = ? WHERE id = ? AND owner_id = ?",
        (int(group_id), group_title, int(link_id), int(owner_id))
    )
    conn.commit()
    return cursor.rowcount > 0

def get_anonymous_link_group(link_id):
    """گرفتن group_id و group_title یه لینک"""
    cursor.execute("SELECT group_id, COALESCE(group_title, '') FROM anonymous_links WHERE id = ?", (int(link_id),))
    row = cursor.fetchone()
    if row:
        return row[0]  # فقط group_id برگردون (برای سازگاری با قبل)
    return 0

def get_anonymous_link_group_info(link_id):
    """گرفتن group_id و group_title یه لینک"""
    cursor.execute("SELECT group_id, COALESCE(group_title, '') FROM anonymous_links WHERE id = ?", (int(link_id),))
    row = cursor.fetchone()
    if row:
        return {"group_id": row[0], "group_title": row[1]}
    return {"group_id": 0, "group_title": ""}

def block_user_from_link(link_id, blocked_user_id):
    """بلاک کاربر از یه لینک خاص"""
    cursor.execute(
        "INSERT OR IGNORE INTO anonymous_link_blocks (link_id, blocked_user_id) VALUES (?, ?)",
        (int(link_id), int(blocked_user_id))
    )
    conn.commit()
    return True

def unblock_user_from_link(link_id, blocked_user_id):
    """درآوردن کاربر از بلاکی یه لینک خاص"""
    cursor.execute(
        "DELETE FROM anonymous_link_blocks WHERE link_id = ? AND blocked_user_id = ?",
        (int(link_id), int(blocked_user_id))
    )
    conn.commit()

def is_user_blocked_from_link(link_id, blocked_user_id):
    """چک کن کاربر برای این لینک بلاک شده یا نه"""
    cursor.execute(
        "SELECT 1 FROM anonymous_link_blocks WHERE link_id = ? AND blocked_user_id = ?",
        (int(link_id), int(blocked_user_id))
    )
    return cursor.fetchone() is not None

def get_blocks_for_user_links(owner_id):
    """گرفتن همه بلاکی‌ها برای لینک‌های یه کاربر"""
    cursor.execute("""
        SELECT alb.link_id, alb.blocked_user_id, al.link_name
        FROM anonymous_link_blocks alb
        JOIN anonymous_links al ON alb.link_id = al.id
        WHERE al.owner_id = ?
    """, (int(owner_id),))
    return [{"link_id": row[0], "blocked_user_id": row[1], "link_name": row[2]} for row in cursor.fetchall()]

def set_anonymous_link_channel(link_id, owner_id, channel_id, channel_title=""):
    """تنظیم کانال برای یه لینک ناشناس (0 یعنی تنظیم نشده)"""
    cursor.execute(
        "UPDATE anonymous_links SET channel_id = ?, channel_title = ? WHERE id = ? AND owner_id = ?",
        (int(channel_id), channel_title, int(link_id), int(owner_id))
    )
    conn.commit()
    return cursor.rowcount > 0

def get_anonymous_link_channel_info(link_id):
    """گرفتن channel_id و channel_title یه لینک"""
    cursor.execute("SELECT COALESCE(channel_id, 0), COALESCE(channel_title, '') FROM anonymous_links WHERE id = ?", (int(link_id),))
    row = cursor.fetchone()
    if row:
        return {"channel_id": row[0], "channel_title": row[1]}
    return {"channel_id": 0, "channel_title": ""}

def set_anonymous_link_security(link_id, setting_name, enabled):
    """تنظیم یه گزینه امنیتی برای لینک"""
    cursor.execute(
        f"UPDATE anonymous_links SET {setting_name} = ? WHERE id = ?",
        (1 if enabled else 0, int(link_id))
    )
    conn.commit()
    return True

def get_anonymous_link_security(link_id):
    """گرفتن تنظیمات امنیتی یه لینک"""
    cursor.execute(
        "SELECT COALESCE(anti_nsfw, 0), COALESCE(anti_badwords, 0), COALESCE(anti_gore, 0) FROM anonymous_links WHERE id = ?",
        (int(link_id),)
    )
    row = cursor.fetchone()
    if row:
        return {"anti_nsfw": bool(row[0]), "anti_badwords": bool(row[1]), "anti_gore": bool(row[2])}
    return {"anti_nsfw": False, "anti_badwords": False, "anti_gore": False}

# ====== توابع مچ‌گیری ======
def create_user_trap(owner_id, link_name="تله"):
    """ساخت تله جدید برای کاربر"""
    import hashlib, time
    token = hashlib.md5(f"help_{owner_id}_{time.time()}".encode()).hexdigest()[:10]
    cursor.execute(
        "INSERT INTO user_traps (owner_id, token, link_name) VALUES (?, ?, ?)",
        (int(owner_id), token, link_name)
    )
    conn.commit()
    return token

def get_user_trap(owner_id):
    """دریافت اطلاعات تله کاربر (جدیدترین)"""
    cursor.execute(
        "SELECT id, token, link_name, welcome_text, welcome_photo, welcome_photo_caption, welcome_media_type, created_at FROM user_traps WHERE owner_id = ? ORDER BY id DESC LIMIT 1",
        (int(owner_id),)
    )
    row = cursor.fetchone()
    if row:
        return {"id": row[0], "token": row[1], "link_name": row[2], "welcome_text": row[3], "welcome_photo": row[4], "welcome_photo_caption": row[5], "welcome_media_type": row[6], "created_at": row[7]}
    return None

def get_all_user_traps(owner_id):
    """دریافت همه تله‌های کاربر"""
    cursor.execute(
        "SELECT id, token, link_name, welcome_text, is_active, hidden_text, created_at FROM user_traps WHERE owner_id = ? ORDER BY id DESC",
        (int(owner_id),)
    )
    return [{"id": row[0], "token": row[1], "link_name": row[2], "welcome_text": row[3], "is_active": row[4], "hidden_text": row[5], "created_at": row[6]} for row in cursor.fetchall()]

def get_trap_by_token(token):
    """پیدا کردن تله با توکن (فقط تله‌های فعال)"""
    cursor.execute(
        "SELECT id, owner_id, link_name, welcome_text, welcome_photo, welcome_photo_caption, welcome_media_type, is_active, hidden_text FROM user_traps WHERE token = ? AND is_active = 1",
        (token,)
    )
    row = cursor.fetchone()
    if row:
        return {
            "id": row[0],
            "owner_id": row[1],
            "link_name": row[2],
            "welcome_text": row[3],
            "welcome_photo": row[4],
            "welcome_photo_caption": row[5],
            "welcome_media_type": row[6],
            "is_active": row[7],
            "hidden_text": row[8] or ""
        }
    return None

def update_trap_welcome(owner_id, welcome_text=None, welcome_photo=None, welcome_photo_caption=None, welcome_media_type=None):
    """آپدیت تنظیمات تله"""
    if welcome_text is not None:
        cursor.execute("UPDATE user_traps SET welcome_text = ? WHERE owner_id = ?", (welcome_text, int(owner_id)))
    if welcome_photo is not None:
        cursor.execute("UPDATE user_traps SET welcome_photo = ? WHERE owner_id = ?", (welcome_photo, int(owner_id)))
    if welcome_photo_caption is not None:
        cursor.execute("UPDATE user_traps SET welcome_photo_caption = ? WHERE owner_id = ?", (welcome_photo_caption, int(owner_id)))
    if welcome_media_type is not None:
        cursor.execute("UPDATE user_traps SET welcome_media_type = ? WHERE owner_id = ?", (welcome_media_type, int(owner_id)))
    conn.commit()

def clear_trap_photo(owner_id):
    """حذف عکس/ویدیو تله"""
    cursor.execute("UPDATE user_traps SET welcome_photo = '', welcome_photo_caption = '' WHERE owner_id = ?", (int(owner_id),))
    conn.commit()

def deactivate_trap(link_id, owner_id):
    """منسوخ کردن یه تله"""
    cursor.execute(
        "UPDATE user_traps SET is_active = 0 WHERE id = ? AND owner_id = ?",
        (int(link_id), int(owner_id))
    )
    conn.commit()
    return cursor.rowcount > 0

def activate_trap(link_id, owner_id):
    """فعال کردن یه تله"""
    cursor.execute(
        "UPDATE user_traps SET is_active = 1 WHERE id = ? AND owner_id = ?",
        (int(link_id), int(owner_id))
    )
    conn.commit()
    return cursor.rowcount > 0

def set_trap_hidden_text(link_id, owner_id, hidden_text):
    """تنظیم متن مخفی برای تله"""
    cursor.execute(
        "UPDATE user_traps SET hidden_text = ? WHERE id = ? AND owner_id = ?",
        (hidden_text, int(link_id), int(owner_id))
    )
    conn.commit()
    return cursor.rowcount > 0

def regenerate_trap_token(link_id, owner_id):
    """تمدید تله (توکن جدید)"""
    import hashlib, time
    new_token = hashlib.md5(f"help_{owner_id}_{link_id}_{time.time()}".encode()).hexdigest()[:10]
    cursor.execute(
        "UPDATE user_traps SET token = ? WHERE id = ? AND owner_id = ?",
        (new_token, int(link_id), int(owner_id))
    )
    conn.commit()
    return new_token if cursor.rowcount > 0 else None

def add_trap_catch(trap_id, user_id, user_name="", user_photo="", user_bio="", username=""):
    """ثبت یه شکار جدید"""
    cursor.execute(
        "INSERT INTO trap_catches (trap_id, user_id, user_name, user_photo, user_bio, username) VALUES (?, ?, ?, ?, ?, ?)",
        (int(trap_id), int(user_id), user_name, user_photo, user_bio, username)
    )
    conn.commit()
    return cursor.lastrowid

def get_trap_catches(owner_id, limit=20):
    """دریافت لیست شکارهای یه کاربر"""
    cursor.execute("""
        SELECT tc.id, tc.user_id, tc.user_name, tc.username, tc.user_photo, tc.user_bio, tc.created_at
        FROM trap_catches tc
        JOIN user_traps ut ON tc.trap_id = ut.id
        WHERE ut.owner_id = ?
        ORDER BY tc.id DESC
        LIMIT ?
    """, (int(owner_id), limit))
    return [{"id": row[0], "user_id": row[1], "user_name": row[2], "username": row[3], "user_photo": row[4], "user_bio": row[5], "created_at": row[6]} for row in cursor.fetchall()]

# ==================== توابع کش فوروارد رسانه ====================
def is_media_forwarded(file_unique_id):
    """چک کن که این فایل قبلاً فوروارد شده یا نه"""
    cursor.execute(
        "SELECT id FROM forwarded_media_cache WHERE file_unique_id = ?",
        (file_unique_id,)
    )
    return cursor.fetchone() is not None

def add_forwarded_media(file_unique_id, file_id, message_id, chat_id):
    """ثبت یک فایل به عنوان فوروارد شده"""
    try:
        cursor.execute(
            """INSERT OR IGNORE INTO forwarded_media_cache
               (file_unique_id, file_id, message_id, chat_id)
               VALUES (?, ?, ?, ?)""",
            (file_unique_id, file_id, message_id, chat_id)
        )
        conn.commit()
        return True
    except Exception as e:
        from logger import error_log
        error_log("add_forwarded_media", str(e))
        return False

def clear_forwarded_media_cache():
    """پاک کردن کامل کش فایل‌های فوروارد شده (با ریست بات)"""
    try:
        cursor.execute("DELETE FROM forwarded_media_cache")
        conn.commit()
        from logger import info
        info("🧹 کش فایل‌های فوروارد شده پاک شد")
        return True
    except Exception as e:
        from logger import error_log
        error_log("clear_forwarded_media_cache", str(e))
        return False

def get_forwarded_media_count():
    """تعداد فایل‌های کش شده رو برگردون"""
    cursor.execute("SELECT COUNT(*) FROM forwarded_media_cache")
    return cursor.fetchone()[0]

# ==================== توابع ناشناس گروهی ====================

def set_group_anonymous_enabled(group_id, enabled):
    """فعال/غیرفعال کردن قابلیت ناشناس گروهی"""
    cursor.execute(
        "INSERT OR REPLACE INTO group_anonymous_settings (group_id, enabled) VALUES (?, ?)",
        (int(group_id), 1 if enabled else 0)
    )
    conn.commit()
    return True

def is_group_anonymous_enabled(group_id):
    """بررسی وضعیت ناشناس گروهی"""
    cursor.execute("SELECT enabled FROM group_anonymous_settings WHERE group_id = ?", (int(group_id),))
    row = cursor.fetchone()
    return row[0] == 1 if row else False

def add_group_anonymous_ban(group_id, user_id, banned_by, message_preview, full_message):
    """بن کردن کاربر از ناشناس گروهی"""
    cursor.execute(
        """INSERT OR REPLACE INTO group_anonymous_bans
           (group_id, user_id, banned_by, message_preview, full_message)
           VALUES (?, ?, ?, ?, ?)""",
        (int(group_id), int(user_id), int(banned_by), message_preview[:50], full_message)
    )
    conn.commit()
    return True

def remove_group_anonymous_ban(group_id, user_id):
    """آزاد کردن کاربر از بن ناشناس گروهی"""
    cursor.execute(
        "DELETE FROM group_anonymous_bans WHERE group_id = ? AND user_id = ?",
        (int(group_id), int(user_id))
    )
    conn.commit()
    return cursor.rowcount > 0

def is_group_anonymous_banned(group_id, user_id):
    """بررسی اینکه کاربر از ناشناس گروهی بن شده یا نه"""
    cursor.execute(
        "SELECT 1 FROM group_anonymous_bans WHERE group_id = ? AND user_id = ?",
        (int(group_id), int(user_id))
    )
    return cursor.fetchone() is not None

def get_group_anonymous_bans(group_id, limit=10, offset=0):
    """دریافت لیست بن‌شده‌های یک گروه با صفحه‌بندی"""
    cursor.execute(
        """SELECT id, user_id, message_preview, full_message, banned_at
           FROM group_anonymous_bans
           WHERE group_id = ?
           ORDER BY id DESC
           LIMIT ? OFFSET ?""",
        (int(group_id), limit, offset)
    )
    return [{"id": row[0], "user_id": row[1], "message_preview": row[2], "full_message": row[3], "banned_at": row[4]} for row in cursor.fetchall()]

def get_group_anonymous_bans_count(group_id):
    """تعداد کل بن‌شده‌های یک گروه"""
    cursor.execute("SELECT COUNT(*) FROM group_anonymous_bans WHERE group_id = ?", (int(group_id),))
    return cursor.fetchone()[0]

def get_group_anonymous_ban_by_id(ban_id):
    """دریافت اطلاعات یک بن با آیدی"""
    cursor.execute(
        "SELECT id, group_id, user_id, message_preview, full_message, banned_at FROM group_anonymous_bans WHERE id = ?",
        (int(ban_id),)
    )
    row = cursor.fetchone()
    if row:
        return {"id": row[0], "group_id": row[1], "user_id": row[2], "message_preview": row[3], "full_message": row[4], "banned_at": row[5]}
    return None

# ==================== توابع پیام‌های ناشناس گروهی ====================

def save_group_anonymous_message(group_id, user_id, message):
    """ذخیره پیام ناشناس گروهی"""
    cursor.execute(
        "INSERT INTO group_anonymous_messages (group_id, from_user_id, message) VALUES (?, ?, ?)",
        (int(group_id), int(user_id), message)
    )
    conn.commit()
    return cursor.lastrowid

def get_group_anonymous_message(msg_id):
    """دریافت پیام ناشناس گروهی با آیدی"""
    cursor.execute(
        "SELECT id, group_id, from_user_id, message, sent_at FROM group_anonymous_messages WHERE id = ?",
        (int(msg_id),)
    )
    row = cursor.fetchone()
    if row:
        return {"id": row[0], "group_id": row[1], "from_user_id": row[2], "message": row[3], "sent_at": row[4]}
    return None

def get_group_anonymous_message(msg_id):
    """دریافت پیام ناشناس گروهی با آیدی"""
    cursor.execute(
        "SELECT id, group_id, from_user_id, message, sent_at FROM group_anonymous_messages WHERE id = ?",
        (int(msg_id),)
    )
    row = cursor.fetchone()
    if row:
        return {"id": row[0], "group_id": row[1], "from_user_id": row[2], "message": row[3], "sent_at": row[4]}
    return None

# ==================== توابع اقدامات روی پیام‌ها ====================

def save_message_action(message_id, user_id, action_type, link_id=None, question_id=None):
    """ذخیره اقدام کاربر روی پیام (گزارش/بن)"""
    cursor.execute("""
        INSERT OR IGNORE INTO message_actions (message_id, user_id, action_type, link_id, question_id)
        VALUES (?, ?, ?, ?, ?)
    """, (int(message_id), int(user_id), action_type, int(link_id) if link_id else None, int(question_id) if question_id else None))
    conn.commit()
    return cursor.rowcount > 0

def has_user_actioned(message_id, user_id, action_type):
    """بررسی اینکه کاربر قبلاً این اقدام رو انجام داده یا نه"""
    cursor.execute(
        "SELECT 1 FROM message_actions WHERE message_id = ? AND user_id = ? AND action_type = ?",
        (int(message_id), int(user_id), action_type)
    )
    return cursor.fetchone() is not None

# ====== ذخیره و بازیابی حالت چت ======
def save_chat_mode(user_id, mode):
    """ذخیره حالت چت کاربر (True=در حالت چت، False=خارج)"""
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO user_ai_settings (user_id, chat_mode) VALUES (?, ?)",
            (int(user_id), 1 if mode else 0)
        )
        conn.commit()
        return True
    except Exception as e:
        from logger import error_log
        error_log("save_chat_mode", f"خطا: {e}")
        return False

def get_chat_mode(user_id):
    """دریافت حالت چت کاربر"""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT chat_mode FROM user_ai_settings WHERE user_id = ?", (int(user_id),))
        row = cursor.fetchone()
        return bool(row[0]) if row else False
    except:
        return False

def get_user_ai_settings(user_id):
    """دریافت تنظیمات AI کاربر"""
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT model_key, category_id FROM user_ai_settings WHERE user_id = ?",
            (int(user_id),)
        )
        row = cursor.fetchone()
        if row:
            return {"model_key": row[0], "category_id": row[1]}
        return None
    except:
        return None

def save_user_ai_settings(user_id, model_key, category_id):
    """ذخیره کامل تنظیمات AI کاربر"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO user_ai_settings (user_id, model_key, category_id)
            VALUES (?, ?, ?)
        """, (int(user_id), model_key, category_id))
        conn.commit()
        return True
    except Exception as e:
        from logger import error_log
        error_log("save_user_ai_settings", f"خطا: {e}")
        return False

def get_group_active_tools_count(chat_id):
    """دریافت تعداد ابزارهای فعال و کل ابزارهای گروه"""
    from settings import get_group_setting

    # لیست تمام ابزارهای قابل شمارش
    tools = [
        # سیستم و خوش‌آمد
        "welcome_status",
        "goodbye_status",
        "is_locked",
        "chatbot_enabled",

        # امنیت و کنترل
        "join_forced",
        "admin_forced",
        "char_limit",
        "bio_link_lock",
        "edit_lock",
        "poll_lock",
        "id_in_bio_lock",
        "bad_name_lock",
        "bad_bio_lock",
        "pv_invite_lock",
        "event_report",
        "msg_limit",

        # رسانه و محتوا
        "anti_spam",
        "anti_link",
        "anti_username",
        "anti_text",
        "anti_photo",
        "anti_video",
        "anti_animation",
        "anti_document",
        "anti_forward",
        "anti_reply",
        "anti_sticker",
        "anti_hashtag",
        "anti_contact",
        "anti_audio",
        "anti_voice",
        "anti_location",
        "anti_badwords",
        "anti_english",
        "anti_toxic",
        "anti_nsfw",
        "anti_gore",
        "anti_media",
        "anti_strange",
        "anti_bot",

        # سیستم و دستورات
        "games_lock",
        "level_system",
        "level_up_notify",
        "fortune_lock",
        "calendar_lock",
        "secret_msg_lock",
        "auto_warn",
        "auto_mute",
    ]

    total_tools = len(tools)
    active_tools = 0

    for tool in tools:
        try:
            value = get_group_setting(chat_id, tool, False)
            if value:
                active_tools += 1
        except:
            pass

    return active_tools, total_tools

# ====== توابع بازنشانی تله ======
def reset_trap_token(link_id, owner_id):
    """بازنشانی توکن تله (تولید توکن جدید)"""
    import hashlib, time
    new_token = hashlib.md5(f"help_{owner_id}_{link_id}_{time.time()}".encode()).hexdigest()[:10]
    cursor.execute(
        "UPDATE user_traps SET token = ?, is_active = 1 WHERE id = ? AND owner_id = ?",
        (new_token, int(link_id), int(owner_id))
    )
    conn.commit()
    return new_token if cursor.rowcount > 0 else None

def delete_trap(link_id, owner_id):
    """حذف کامل تله"""
    cursor.execute(
        "DELETE FROM user_traps WHERE id = ? AND owner_id = ?",
        (int(link_id), int(owner_id))
    )
    conn.commit()
    return cursor.rowcount > 0

def get_user_actions_on_message(message_id, user_id):
    """دریافت لیست اقدامات انجام‌شده توسط کاربر روی یک پیام"""
    cursor.execute(
        "SELECT action_type FROM message_actions WHERE message_id = ? AND user_id = ?",
        (int(message_id), int(user_id))
    )
    return [row[0] for row in cursor.fetchall()]

# ====== راه‌اندازی ======
init_db()
migrate_database()
