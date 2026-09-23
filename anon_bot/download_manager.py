# download_manager.py
import os
import requests
import threading
import time
import shutil
from config import TOKEN, BASE_URL

# پوشه دانلود موقت
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

# دیکشنری برای ذخیره زمان دانلود فایل‌ها
_downloaded_files = {}  # {file_path: download_time}

def _cleanup_old_files():
    """پاک کردن فایل‌های قدیمی‌تر از 60 ثانیه"""
    now = time.time()

    # ⭐ روش ۱: پاک کردن از روی دیکشنری
    to_delete = []
    for file_path, download_time in _downloaded_files.items():
        if now - download_time > 60:
            to_delete.append(file_path)

    for file_path in to_delete:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️ پاک شد: {file_path}")
            del _downloaded_files[file_path]
        except Exception as e:
            print(f"⚠️ خطا در پاک کردن {file_path}: {e}")

    # ⭐ روش ۲: پاکسازی کل پوشه temp از فایل‌های قدیمی
    try:
        for filename in os.listdir(TEMP_DIR):
            file_path = os.path.join(TEMP_DIR, filename)
            if os.path.isfile(file_path):
                file_age = now - os.path.getmtime(file_path)
                if file_age > 60:
                    try:
                        os.remove(file_path)
                        print(f"🗑️ پاک شد (از روی تاریخ): {filename}")
                    except:
                        pass
    except Exception as e:
        print(f"⚠️ خطا در پاکسازی پوشه: {e}")

def _start_cleanup_thread():
    """اجرای خودکار پاک کردن هر 10 ثانیه"""
    def cleanup_loop():
        while True:
            time.sleep(10)
            _cleanup_old_files()

    thread = threading.Thread(target=cleanup_loop, daemon=True)
    thread.start()

# شروع线程 پاکسازی خودکار
_start_cleanup_thread()

def download_file(file_id, file_type="general"):
    try:
        # ⭐ برای ویدیو، پیشوند "video:" رو حذف کن
        if file_id.startswith("video:"):
            file_id = file_id.replace("video:", "")

        download_url = f"https://tapi.bale.ai/file/bot{TOKEN}/{file_id}"
        response = requests.get(download_url, stream=True, timeout=60)

        if response.status_code != 200:
            print(f"❌ دانلود ناموفق [{file_type}]: {response.status_code}")
            return None

        temp_dir = TEMP_DIR
        os.makedirs(temp_dir, exist_ok=True)

        if file_type == "photo" or file_type == "nsfw":
            ext = '.jpg'
        elif file_type == "gore":
            ext = '.jpg'
        elif file_type == "video":
            ext = '.mp4'
        else:
            ext = '.bin'

        import hashlib
        hash_name = hashlib.md5(f"{file_id}_{time.time()}".encode()).hexdigest()[:16]
        local_path = os.path.join(temp_dir, f"{file_type}_{hash_name}{ext}")

        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        file_size = os.path.getsize(local_path)
        if file_size < 100:
            os.remove(local_path)
            return None

        print(f"✅ دانلود شد [{file_type}]: {os.path.basename(local_path)} ({file_size} bytes)")
        return local_path

    except Exception as e:
        print(f"Download error [{file_type}]: {e}")
        return None

def _get_extension(file_id, response):
    """تشخیص پسوند فایل"""
    # اول از روی file_type (پارامتری که به download_file داده می‌شود)
    # این رو باید از پارامتر file_type بگیریم

    # از روی file_id
    if 'photo' in file_id.lower():
        return '.jpg'
    elif 'video' in file_id.lower():
        return '.mp4'
    elif 'animation' in file_id.lower():
        return '.mp4'

    # از روی Content-Type
    content_type = response.headers.get('Content-Type', '')
    if 'image' in content_type:
        return '.jpg'
    elif 'video' in content_type:
        return '.mp4'

    return '.bin'

def download_and_get_path(file_id, file_type="general"):
    """
    دانلود فایل و برگرداندن مسیر (همان download_file)
    این تابع برای سازگاری با کدهای قدیمی
    """
    return download_file(file_id, file_type)

def cleanup_now():
    """پاکسازی فوری همه فایل‌های قدیمی"""
    _cleanup_old_files()

def get_temp_dir():
    """برگرداندن مسیر پوشه temp"""
    return TEMP_DIR
