"""
تنظیمات ربات آب‌وهوا
Pydantic-free configuration. Environment variables take precedence.
"""

import os
from pathlib import Path

# ─── توکن ربات تلگرام ────────────────────────────────────────────────
# این مقدار از .env یا متغیر محیطی TELEGRAM_BOT_TOKEN خوانده می‌شود
# مقدار پیش‌فرض همان توکنی است که کاربر ارسال کرده است.
BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "8942517880:AAHlg40tokof3sxbjZgWSfp3LWzRC96J28k",
)

# ─── تنظیمات کلی ─────────────────────────────────────────────────────
DEFAULT_LANGUAGE = "fa"          # زبان پیش‌فرض نام شهرها (در Open-Meteo Geocoding)
DEFAULT_TIMEZONE = "auto"        # منطقه‌زمانی خودکار بر اساس موقعیت
DEFAULT_UNIT = "metric"          # سانتی‌گراد، کیلومتر بر ساعت، میلی‌متر

# پیش‌بینی روزانه به تعداد روز
FORECAST_DAYS = 3

# پیش‌بینی ساعتی به تعداد ساعت
HOURLY_HOURS = 24

# تعداد نتایج جستجوی شهر هنگام ambiguity
GEOCODING_MAX_RESULTS = 5

# ─── آدرس‌های API ─────────────────────────────────────────────────────
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

# ─── مسیرها ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FAVORITES_FILE = DATA_DIR / "favorites.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# ─── پیام‌های ثابت ────────────────────────────────────────────────────
WELCOME_MESSAGE = (
    "👋 سلام! به ربات آب‌وهوا خوش آمدید.\n\n"
    "این ربات با استفاده از سرویس رایگان Open-Meteo اطلاعات آب‌وهوا را "
    "برای شما نمایش می‌دهد.\n\n"
    "📝 دستورات موجود:\n"
    "/weather - آب‌وهوای فعلی\n"
    "/forecast - پیش‌بینی ۳ روزه\n"
    "/hourly - پیش‌بینی ۲۴ ساعت آینده\n"
    "/favorites - مدیریت شهرهای موردعلاقه\n"
    "/add <نام شهر> - افزودن شهر به علاقه‌مندی‌ها\n"
    "/remove <نام شهر> - حذف شهر از علاقه‌مندی‌ها\n"
    "/help - راهنمایی\n\n"
    "💡 همچنین می‌توانید لوکیشن (موقعیت مکانی) خود را ارسال کنید تا "
    "آب‌وهوای همان نقطه را دریافت کنید."
)

HELP_MESSAGE = (
    "📖 راهنمای استفاده از ربات آب‌وهوا\n\n"
    "🌤 آب‌وهوای فعلی:\n"
    "   /weather تهران\n"
    "   یا فقط /weather برای انتخاب از علاقه‌مندی‌ها\n\n"
    "📅 پیش‌بینی ۳ روزه:\n"
    "   /forecast شیراز\n\n"
    "⏰ پیش‌بینی ساعتی (۲۴ ساعت آینده):\n"
    "   /hourly مشهد\n\n"
    "⭐ مدیریت علاقه‌مندی‌ها:\n"
    "   /add اصفهان\n"
    "   /remove اصفهان\n"
    "   /favorites - نمایش لیست\n\n"
    "📍 ارسال موقعیت:\n"
    "   دکمه گیره (📎) → Location → موقعیت خود را ارسال کنید\n\n"
    "🔍 می‌توانید نام شهر را به فارسی یا انگلیسی بنویسید."
)
