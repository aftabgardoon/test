# Multi-Channel Sync Bot

بات همگام‌سازی چندکاناله برای **بله**، **ایتا** و **روبیکا**. پیام‌های ارسال‌شده در یک
کانال مبدأ (متن، عکس با کپشن، ویدیو، ویس، فایل، استیکر، لوکیشن و دکمه‌های شیشه‌ای) به
صورت خودکار و با حفظ ظاهر، در چند کانال مقصد بازنشر می‌شوند. سیستم **چندکاربره (Multi-Tenant)**
است: هر کاربر کانال‌ها و ربات‌های خودش را ثبت می‌کند و بات برای او همگام‌سازی انجام می‌دهد.

> **⚠️ هشدار:** استفاده از API غیررسمی روبیکا ممکن است باعث محدودیت، تغییر ناگهانی یا مسدود شدن
> شود. برای ایتا نیز API رسمی امکان دریافت لحظه‌ای پیام کانال را نمی‌دهد (توضیح در بخش محدودیت‌ها).

---

## معماری

```
┌──────────────┐   long polling    ┌───────────────┐   enqueue   ┌─────────┐
│ Bale / Rubika│ ────────────────▶ │    Pollers    │ ──────────▶ │  Redis  │
│  (source)    │   getUpdates      │ (app/pollers) │             │ / memory│
└──────────────┘                   └───────────────┘             └────┬────┘
                                                                       │ dequeue
                                                                       ▼
┌──────────────┐  send / copy / upload  ┌───────────────┐  process   ┌─────────┐
│ Bale/Eitaa/  │ ◀────────────────────── │    Worker     │ ◀───────── │  Job    │
│ Rubika (dest)│                        │ (sync_service)│            └─────────┘
└──────────────┘                        └───────────────┘
```

- **Core**: `app/services/sync_service.py` — منطق همگام‌سازی، فیلترها، retry و لاگ.
- **Adapters**: هر پیام‌رسان یک آداپتور با اینترفیس یکسان (`app/adapters/base.py`).
- **Pollers**: دریافت پیام‌های مبدأ با Long Polling (`app/pollers/`).
- **Bot Manager**: ربات تعاملی (پیش‌فرض بله) که کاربران با آن کانال/توکن ثبت می‌کنند.
- **Database**: SQLAlchemy 2.0 async (PostgreSQL/asyncpg یا SQLite/aiosqlite).
- **Queue**: Redis (لیست) یا صف درون‌حافظه‌ای برای توسعه و تست.
- **API Server**: FastAPI — فقط برای health check و (در آینده) پنل ادمین.

## ساختار پوشه‌ها

```
multichannel-sync-bot/
├── app/
│   ├── main.py                  # entrypoint FastAPI + lifespan
│   ├── config.py                # pydantic-settings
│   ├── database.py              # engine/session/Base
│   ├── queue.py                 # Redis / in-memory queue
│   ├── models/                  # SQLAlchemy models (user, channel, sync_link, message_log, bot_token)
│   ├── schemas/                 # Pydantic schemas
│   ├── adapters/                # base, bale, eitaa, rubika + factory
│   ├── services/                # sync_service, channel_service, user_service, token_service
│   ├── bot_manager/             # handlers, keyboards, states, manager (polling)
│   ├── pollers/                 # base, bale_poller, rubika_poller, eitaa_poller
│   ├── workers/sync_worker.py   # مصرف‌کننده صف پیام
│   └── utils/                   # crypto (Fernet), logger (loguru)
├── migrations/                  # alembic (env.py, versions/0001_initial.py)
├── tests/                       # pytest (adapters, sync_service)
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── pyproject.toml
```

---

## نصب و راه‌اندازی

### پیش‌نیازها

- Python 3.11+
- (اختیاری) Docker و Docker Compose
- (اختیاری) PostgreSQL و Redis

### راه‌اندازی محلی (توسعه)

```bash
cd multichannel-sync-bot
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env   # سپس مقادیر را پر کنید

# ساخت جداول (یا اجرای migration)
alembic upgrade head

# اجرای سرور (polling + مدیر + ورکر درون‌حافظه‌ای)
python -m app.main
# یا:
uvicorn app.main:app --port 8000
```

برای اجرای جداگانهٔ مدیر و ورکر:

```bash
python -m app.bot_manager.manager
python -m app.workers.sync_worker
```

### راه‌اندازی با Docker

```bash
cp .env.example .env   # مقادیر را پر کنید
docker compose up --build
```

سرویس‌ها: `app` (FastAPI)، `worker` (مصرف‌کننده صف Redis)، `postgres`، `redis`.

### Migration

```bash
# ساخت migration جدید (autogenerate)
alembic revision --autogenerate -m "message"

# اعمال migration
alembic upgrade head
```

---

## متغیرهای محیطی (`.env`)

| متغیر | توضیح | پیش‌فرض |
|---|---|---|
| `DATABASE_URL` | آدرس دیتابیس (asyncpg/aiosqlite) | `sqlite+aiosqlite:///./syncbot.db` |
| `REDIS_URL` | آدرس Redis | `redis://redis:6379/0` |
| `QUEUE_ENABLED` | استفاده از Redis (`true`) یا صف حافظه (`false`) | `false` |
| `FERNET_KEY` | کلید رمزنگاری توکن‌ها (Fernet) | مشتق از `WEBHOOK_SECRET` (فقط توسعه) |
| `WEBHOOK_SECRET` | کلید پشتیبان برای ساخت کلید Fernet | — |
| `MANAGER_BOT_TOKEN` | توکن ربات مدیریت (می‌تواند با `BALE_BOT_TOKEN` یکی باشد؛ حالت تک‌بات) | — |
| `MANAGER_BOT_PLATFORM` | پلتفرم ربات مدیریت | `bale` |
| `MANAGER_ACCESS_SECRET` | رمز باز کردن رابط ربات مدیریت؛ کاربر باید `/RSAsecret <value>` بفرستد. خالی = بدون قفل | `RSAsecret` |
| `BALE_BOT_TOKEN` | توکن ربات شنوندهٔ بله (باید ادمین کانال مبدأ باشد) | — |
| `RUBIKA_BOT_TOKEN` | توکن ربات شنوندهٔ روبیکا | — |
| `EITAA_BOT_TOKEN` | توکن ربات ایتا (فقط مقصد) | — |
| `POLLING_ENABLED` | فعال بودن Long Polling | `true` |
| `POLLING_TIMEOUT` | مدت long-polling هر درخواست `getUpdates` (ثانیه) | `15` |
| `POLLING_RETRY_DELAY` | تأخیر بین تلاش مجدد پس از خطا (ثانیه) | `5.0` |
| `WORKER_CONCURRENCY` | تعداد پیام‌هایی که ورکر به‌صورت موازی ارسال می‌کند | `20` |
| `RATE_LIMIT_RPS` | سقف پیام بر ثانیه هر آداپتور | `30` |
| `RETRY_ATTEMPTS` / `RETRY_BACKOFF_BASE` | تعداد و ضریب backoff تلاش مجدد | `3` / `1.5` |

تولید کلید Fernet:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## گرفتن توکن ربات

### بله (Bale)
1. در بله با [@BotFather](https://ble.ir/botfather) (یا معادل آن) چت کنید.
2. `/newbot` بزنید و نام ربات را وارد کنید.
3. توکن دریافتی را در فایل `.env` (متغیر `BALE_BOT_TOKEN` برای شنونده و
   `MANAGER_BOT_TOKEN` برای ربات مدیریت) قرار دهید.
4. مستندات: https://docs.bale.ai

### ایتا (Eitaa)
1. به [eitaayar.ir](https://eitaayar.ir) وارد شوید و در بخش «ساخت ربات» ربات بسازید.
2. توکن را در `.env` (متغیر `EITAA_BOT_TOKEN`) قرار دهید.
3. مستندات API: https://eitaayar.ir/api

### روبیکا (Rubika)
1. از طریق Bot API روبیکا (یا ابزارهای جامعه) توکن ربات بگیرید.
2. توکن را در `.env` (متغیر `RUBIKA_BOT_TOKEN`) قرار دهید.
> API رسمی روبیکا پایدار نیست؛ آداپتور به‌راحتی قابل تعویض است.

---

## قفل دسترسی ربات مدیریت (`/RSAsecret`)

رابط ربات مدیریت به‌صورت پیش‌فرض **قفل** است: تا وقتی کاربر دستور مخفی را نفرستد،
هیچ منو/پیامی نمی‌بیند.

- مقدار قفل در `MANAGER_ACCESS_SECRET` است (پیش‌فرض: `RSAsecret`).
- کاربر باید `/RSAsecret <value>` بفرستد؛ اگر مقدار همان پیش‌فرض باشد، فرستادن
  `/RSAsecret` تنها کافی است.
- بعد از باز شدن، دسترسی در جدول `authorized_users` ذخیره می‌شود و بعد از ری‌استارت
  هم باقی می‌ماند.
- برای **غیرفعال‌کردن** قفل، `MANAGER_ACCESS_SECRET` را خالی بگذارید.
- جواب اشتباه هیچ پیامی برنمی‌گرداند (ربات وجود خودش را لو نمی‌دهد).

> ⚠️ دستور `/RSAsecret` در چت خصوصی کار می‌کند؛ پست‌های کانال هرگز به‌عنوان ورودی
> مدیر پاسخ داده نمی‌شوند.

### پیام `/start` (لندینگ عمومی + لینک ناشناس)

- `/start` برای همه (حتی بدون قفل) پیام معرفی ربات پیام ناشناس را نشان می‌دهد،
  همراه دکمه‌ی اینلاین «🔗 لینک ناشناس».
- با زدن آن دکمه، **تمام فرآیندهای ربات پیام ناشناس داخل همین ربات** اجرا
  می‌شود (ساخت لینک، دریافت پیام ناشناس، پنل مدیریت، بلاک، پاسخ و...).
- کد ربات ناشناس در پوشه‌ی `anon_bot/` قرار دارد و با توکن همین ربات اجرا
  می‌شود (توسط `app/anon_bridge.py`).
- `/RSAsecret` پس از باز کردن قفل، پیام اول/منوی ربات همگام‌سازی را نشان می‌دهد.

---

## ادمین کردن ربات در کانال

برای اینکه ربات بتواند پیام کانال را بخواند (مبدأ) یا در آن ارسال کند (مقصد):

1. ربات مربوط به همان پلتفرم را به کانال اضافه کنید.
2. ربات را **ادمین (Admin)** کانال کنید.
3. اگر کانال مبدأ است، باید دسترسی خواندن پیام به ربات داده شود.

برای **بله** و **روبیکا** (مبدأ): ربات ادمین، پیام‌های جدید را از طریق Long Polling
دریافت می‌کند.

برای **ایتا**: فقط مقصد؛ کافی است ربات در کانال مقصد ادمین باشد.

---

## Long Polling چطور کار می‌کند

این پروژه به‌جای webhook از **Long Polling** استفاده می‌کند تا نیازی به دامنه، HTTPS یا
سرور عمومی نداشته باشید و بتوانید همه‌چیز را روی سیستم لوکال اجرا کنید.

- هر پلتفرم مبدأ (بله/روبیکا) یک **Poller** دارد که در یک حلقه، `getUpdates` را با
  `timeout=POLLING_TIMEOUT` صدا می‌زند (درخواست HTTP تا رسیدن پیام جدید باز نگه داشته می‌شود).
- `offset` آخرین پیام پردازش‌شده نگه داشته می‌شود تا پیامی دوباره پردازش نشود.
- هر update به `IncomingMessage` تبدیل و به `sync_service` داده می‌شود و سپس وارد صف و ورکر می‌شود.
- در صورت خطا، با `loguru` لاگ می‌شود و بعد از `POLLING_RETRY_DELAY` ثانیه دوباره تلاش می‌کند.
- ایتا چون مبدأ نیست، هیچ Poller ای برایش ساخته نمی‌شود.
- **API روبیکا long-polling ندارد**؛ Poller روبیکا بلافاصله پاسخ می‌گیرد و برای جلوگیری از
  spin بین هر `getUpdates` یک مکث کوتاه می‌زند.

### حالت تک‌بات (یک توکن، دو وظیفه)

می‌توانید `MANAGER_BOT_TOKEN` را **مساوی** `BALE_BOT_TOKEN` بگذارید تا همان ربات هم ربات
مدیر باشد و هم پیام‌های کانال مبدأ را بخواند. در این حالت:

- حلقهٔ مدیریت (`run_manager`) تنها مصرف‌کنندهٔ `getUpdates` است؛ Poller جداگانه‌ای برای
  همان توکن ساخته **نمی‌شود** (پس دو مصرف‌کننده روی یک توکن نمی‌چرخند و offset ها تداخل نمی‌کنند).
- آپدیت‌های کانال (channel_post / chat غیر خصوصی) مستقیماً به `sync_service.dispatch_sync_update`
  داده می‌شوند و فقط چت‌های خصوصی به دستورات/دکمه‌های مدیر پاسخ می‌دهند.

> برای production با ترافیک بالا، توصیه می‌شود بعداً به **webhook** مهاجرت کنید (تأخیر کمتر و
> مصرف منابع کمتر)؛ در آن صورت فقط لایهٔ `app/pollers` با یک ماژول webhook جایگزین می‌شود و
> بقیهٔ منطق (`sync_service`، آداپتورها، ورکر) بدون تغییر باقی می‌ماند.

---

## تست با یک کانال نمونه

1. توکن ربات‌های شنونده را در `.env` قرار دهید (`BALE_BOT_TOKEN`/`RUBIKA_BOT_TOKEN`).
2. ربات مدیریت را با `/start` اجرا کنید.
3. `/addchannel` → کانال مبدأ و مقصد را ثبت کنید.
4. `/setsource` → کانال مبدأ را مشخص کنید.
5. `/adddest` → کانال مقصد را انتخاب کنید تا لینک ساخته شود.
6. یک پیام متنی یا عکس در کانال مبدأ ارسال کنید → باید در مقصد منتشر شود.
7. `/links` → وضعیت لینک‌ها، `/pause` و `/resume` برای فعال/غیرفعال کردن.

---

## تست‌های خودکار

```bash
pytest
```

تست‌ها از SQLite و صف درون‌حافظه‌ای استفاده می‌کنند (بدون نیاز به سرویس خارجی).

---

## محدودیت‌ها و نکات مهم

1. **ایتا فقط مقصد است.** API رسمی ایتا امکان دریافت لحظه‌ای پیام کانال را نمی‌دهد؛ بنابراین ایتا
   هرگز به‌عنوان مبدأ استفاده نمی‌شود (`supports_source=False`).
2. **بله و روبیکا** هم مبدأ و هم مقصد پشتیبانی می‌شوند.
3. **حفظ ظاهر پیام (بدون برچسب «فوروارد شده از…»)**:
   - بله: `copyMessage` (سریع و بدون برچسب).
   - روبیکا و ایتا: دانلود از مبدأ و آپلود مجدد با `sendFile`/`sendPhoto`.
   - پیام فورواردشده از کانال دیگر نیز به‌صورت محتوای اصلی بازنشر می‌شود.
4. **Rate limit**: هر آداپتور با `RATE_LIMIT_RPS` محدود می‌شود (بله ~۳۰ پیام/ثانیه).
5. **دکمه‌های شیشه‌ای با `callback_data`** در مقصد فقط به‌صورت URL کار می‌کنند؛
   `callback_data` به پلتفرم دیگر قابل انتقال نیست.
6. **ویرایش/حذف پیام**: در صورت پشتیبانی پلتفرم، ویرایش/حذف مبدأ به مقصد منتقل می‌شود
   (بله پشتیبانی کامل دارد؛ روبیکا/ایتا بسته به API).
7. **API غیررسمی روبیکا** ممکن است محدود یا تغییر کند؛ آداپتور آن ایزوله و قابل تعویض است.
8. **توکن‌ها** با Fernet رمزنگاری می‌شوند و هرگز در لاگ نمایش داده نمی‌شوند.
9. **دریافت پیام** با Long Polling انجام می‌شود (نیازی به دامنه/HTTPS نیست).
10. **پایین‌آمدی مدیا در API بله** (طبق مستندات docs.bale.ai):
    - بله متد `sendPoll` ندارد؛ نظرسنجی‌ها به‌صورت **متن** بازنشر می‌شوند.
    - بله متد `sendSticker` ندارد؛ استیکرها ابتدا به‌صورت استیکر و در صورت خطا
      (بدون تغییر) به‌عنوان عکس/فایل ارسال می‌شوند.
    - ایتا نیز `sendPoll` ندارد؛ نظرسنجی‌ها به‌صورت متن ارسال می‌شوند.
    - پارامتر `parse_mode` در API بله وجود ندارد؛ متن همیشه Markdown است و این
      پارامتر از payload حذف می‌شود.
    - `copyMessage` بله فقط ۳ پارامتر می‌گیرد (بدون caption/reply_markup)؛
      کپی، محتوای اصلی پیام را شامل کپشن و کلیدورد منتقل می‌کند.
11. **مدیا به‌صورت بومی**: فایل‌های صوتی با `sendAudio` بله (پلیر موسیقی،
    mp3/m4a) و نوع `Music` روبیکا ارسال می‌شوند، نه به‌صورت فایل معمولی.
    انیمیشن‌های GIF در بله به‌صورت فایل (document) بازنشر می‌شوند.
12. **حدود حجم** (طبق مستندات): آپلود در بله حداکثر ۱۰MB برای تصویر و
    ۵۰MB برای بقیه؛ در روبیکا ۱۰MB برای Image و ۵۰MB برای Video/File؛
    دانلود فایل در بله حداکثر ۲۰MB.

---

## معیارهای پذیرش

- [x] تعامل با ربات مدیریت و ثبت کانال
- [x] عضویت ربات به‌عنوان ادمین در بله/روبیکا
- [x] انتشار پیام متنی بله → روبیکا/ایتا
- [x] کپی عکس (با کپشن)، ویس، ویدیو و فایل
- [x] حذف پیام مبدأ → حذف در مقصد (در پلتفرم‌های پشتیبانی‌شده)
- [x] ثبت خطاها در `message_logs` و retry
- [x] اجرا با `docker compose up`
- [x] پاس شدن تست‌ها با `pytest`
