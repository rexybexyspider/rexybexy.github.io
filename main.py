"""
ربات تلگرام آب‌وهوا — Open-Meteo
نقطه ورودی اصلی و هندلرهای پیام.

اجرا:
    python main.py

متغیرهای محیطی (اختیاری):
    TELEGRAM_BOT_TOKEN   — توکن ربات (پیش‌فرض: مقدار در config.py)
    LOG_LEVEL            — سطح لاگ (پیش‌فرض: INFO)
"""

from __future__ import annotations

import logging
import sys

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from storage import favorites as fav_store
from utils import (
    back_to_menu_keyboard,
    city_action_keyboard,
    disambiguation_keyboard,
    favorite_cities_keyboard,
    format_jalalian_date,
    main_menu_keyboard,
    render_current_weather,
    render_daily_forecast,
    render_favorites,
    render_hourly_forecast,
)
from weather import (
    CityNotFoundError,
    GeoLocation,
    WeatherAPIError,
    weather_client,
)

# ─── لاگ‌گذاری ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
# کاهش نویز کتابخانه‌ها
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.INFO)

logger = logging.getLogger("weather_bot")


# ─── توابع کمکی عمومی ────────────────────────────────────────────────
async def send_error(
    update: Update, message: str, **kwargs
) -> None:
    """ارسال پیام خطا به کاربر."""
    if update.effective_message:
        await update.effective_message.reply_text(
            f"⚠️ {message}", **kwargs
        )


def parse_callback_location(data: str) -> GeoLocation:
    """
    پارس callback_data برای استخراج نام و مختصات.
    فرمت: city:<action>:<name_en>:<lat>,<lon>
          favadd:<name_en>:<lat>,<lon>
    """
    parts = data.split(":")
    name_en = parts[-2] if len(parts) >= 3 else "City"
    coord_str = parts[-1]
    lat_str, lon_str = coord_str.split(",")
    return GeoLocation(
        name=name_en,
        name_en=name_en,
        latitude=float(lat_str),
        longitude=float(lon_str),
    )


async def resolve_city(
    city_name: str, action: str = "weather"
) -> tuple[GeoLocation | None, list[GeoLocation]]:
    """
    حل نام شهر.
    برمی‌گرداند: (شهر یکتا، یا None و لیست کاندیدها)
    """
    try:
        results = await weather_client.geocode(city_name)
    except CityNotFoundError:
        return None, []
    except WeatherAPIError:
        return None, []

    if len(results) == 1:
        return results[0], []
    return None, results


# ─── هندلرهای دستورات ────────────────────────────────────────────────
async def start_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """دستور /start — پیام خوش‌آمدگویی و منو."""
    await update.effective_message.reply_text(
        config.WELCOME_MESSAGE,
        reply_markup=main_menu_keyboard(),
    )


async def help_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """دستور /help — راهنما."""
    await update.effective_message.reply_text(config.HELP_MESSAGE)


async def weather_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    دستور /weather [city]
    اگر شهر داده نشد و علاقه‌مندی داشت → کیبورد انتخاب
    اگر شهر داده شد → آب‌وهوا
    """
    args = context.args
    if not args:
        # اگر علاقه‌مندی داشت
        if fav_store.list(update.effective_user.id):
            await update.effective_message.reply_text(
                "یکی از شهرهای موردعلاقه خود را انتخاب کنید:",
                reply_markup=favorite_cities_keyboard(
                    update.effective_user.id, action="weather"
                ),
            )
        else:
            await update.effective_message.reply_text(
                "لطفاً نام شهر را وارد کنید.\n\n"
                "مثال: /weather تهران"
            )
        return

    city_name = " ".join(args)
    await _send_weather_for_city(update, city_name)


async def forecast_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """دستور /forecast [city] — پیش‌بینی ۳ روزه."""
    args = context.args
    if not args:
        if fav_store.list(update.effective_user.id):
            await update.effective_message.reply_text(
                "یکی از شهرهای موردعلاقه خود را انتخاب کنید:",
                reply_markup=favorite_cities_keyboard(
                    update.effective_user.id, action="forecast"
                ),
            )
        else:
            await update.effective_message.reply_text(
                "لطفاً نام شهر را وارد کنید.\n\n"
                "مثال: /forecast تهران"
            )
        return

    city_name = " ".join(args)
    await _send_forecast_for_city(update, city_name)


async def hourly_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """دستور /hourly [city] — پیش‌بینی ۲۴ ساعت آینده."""
    args = context.args
    if not args:
        if fav_store.list(update.effective_user.id):
            await update.effective_message.reply_text(
                "یکی از شهرهای موردعلاقه خود را انتخاب کنید:",
                reply_markup=favorite_cities_keyboard(
                    update.effective_user.id, action="hourly"
                ),
            )
        else:
            await update.effective_message.reply_text(
                "لطفاً نام شهر را وارد کنید.\n\n"
                "مثال: /hourly تهران"
            )
        return

    city_name = " ".join(args)
    await _send_hourly_for_city(update, city_name)


async def add_favorite_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """دستور /add <city> — افزودن شهر به علاقه‌مندی‌ها."""
    if not context.args:
        await update.effective_message.reply_text(
            "لطفاً نام شهر را وارد کنید.\n\n"
            "مثال: /add تهران"
        )
        return

    city_name = " ".join(context.args)
    single, candidates = await resolve_city(city_name, action="favadd")
    if single is None:
        if not candidates:
            await update.effective_message.reply_text(
                f"⚠️ شهری با نام «{city_name}» یافت نشد.\n"
                "لطفاً نام را به‌دقت وارد کنید."
            )
        else:
            await update.effective_message.reply_text(
                f"چند شهر با نام «{city_name}» یافت شد. کدام منظور شماست؟",
                reply_markup=disambiguation_keyboard(
                    candidates, action="favadd"
                ),
            )
        return

    added = fav_store.add(update.effective_user.id, single)
    if added:
        await update.effective_message.reply_text(
            f"✅ «{single.display}» به علاقه‌مندی‌های شما اضافه شد."
        )
    else:
        await update.effective_message.reply_text(
            f"ℹ️ «{single.display}» از قبل در علاقه‌مندی‌های شما وجود دارد."
        )


async def remove_favorite_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """دستور /remove <city> — حذف شهر از علاقه‌مندی‌ها."""
    if not context.args:
        await update.effective_message.reply_text(
            "لطفاً نام شهر را وارد کنید.\n\n"
            "مثال: /remove تهران"
        )
        return

    city_name = " ".join(context.args)
    removed = fav_store.remove(update.effective_user.id, city_name)
    if removed:
        await update.effective_message.reply_text(
            f"🗑 «{city_name}» از علاقه‌مندی‌های شما حذف شد."
        )
    else:
        await update.effective_message.reply_text(
            f"⚠️ «{city_name}» در علاقه‌مندی‌های شما یافت نشد.\n\n"
            "برای مشاهده لیست: /favorites"
        )


async def favorites_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """دستور /favorites — نمایش لیست علاقه‌مندی‌ها."""
    favs = fav_store.list(update.effective_user.id)
    await update.effective_message.reply_text(
        render_favorites(favs),
        reply_markup=favorite_cities_keyboard(
            update.effective_user.id, action="weather"
        ) if favs else back_to_menu_keyboard(),
    )


async def dev_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """دستور /dev — اطلاعات توسعه‌دهنده ربات."""
    await update.effective_message.reply_text(
        "👨‍💻 طراحی: محمد Y"
    )


# ─── هندلر موقعیت مکانی ──────────────────────────────────────────────
async def location_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """هنگام ارسال لوکیشن توسط کاربر."""
    loc = update.effective_message.location
    if not loc:
        return

    await update.effective_message.reply_text(
        "📍 در حال دریافت آب‌وهوای موقعیت شما..."
    )

    try:
        geo = await weather_client.reverse_geocode(loc.latitude, loc.longitude)
        weather = await weather_client.get_weather(geo)
    except WeatherAPIError as e:
        await send_error(update, str(e))
        return

    text = render_current_weather(geo, weather)
    await update.effective_message.reply_text(
        text, reply_markup=city_action_keyboard(geo)
    )


# ─── هندلر callback های دکمه‌های شیشه‌ای ──────────────────────────────
async def callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """مدیریت کلیک روی دکمه‌های شیشه‌ای."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    # پاک کردن صفحه کیبورد قبلی
    try:
        await query.message.delete_reply_markup()
    except Exception:
        pass

    # ── منوی اصلی ──────────────────────────────────────────────────
    if data == "menu":
        await query.message.reply_text(
            "🏠 منوی اصلی:", reply_markup=main_menu_keyboard()
        )
        return

    if data == "help":
        await query.message.reply_text(
            config.HELP_MESSAGE, reply_markup=back_to_menu_keyboard()
        )
        return

    # ── انتخاب نوع آب‌وهوا ────────────────────────────────────────
    if data in {"weather", "forecast", "hourly"}:
        favs = fav_store.list(user_id)
        if favs:
            await query.message.reply_text(
                "یکی از شهرهای موردعلاقه خود را انتخاب کنید "
                "یا نام شهر جدید را با دستور مربوطه وارد کنید:",
                reply_markup=favorite_cities_keyboard(
                    user_id, action=data
                ),
            )
        else:
            cmd = {
                "weather": "/weather",
                "forecast": "/forecast",
                "hourly": "/hourly",
            }[data]
            await query.message.reply_text(
                f"هیچ شهر ذخیره‌شده‌ای ندارید.\n"
                f"برای دریافت اطلاعات از دستور {cmd} <نام شهر> استفاده کنید "
                "یا ابتدا با /add شهر اضافه کنید.",
                reply_markup=back_to_menu_keyboard(),
            )
        return

    # ── مدیریت علاقه‌مندی‌ها ──────────────────────────────────────
    if data == "favorites":
        favs = fav_store.list(user_id)
        await query.message.reply_text(
            render_favorites(favs),
            reply_markup=favorite_cities_keyboard(
                user_id, action="weather"
            ) if favs else back_to_menu_keyboard(),
        )
        return

    # ── افزودن سریع به علاقه‌مندی ─────────────────────────────────
    if data.startswith("favadd:"):
        try:
            loc = parse_callback_location(data)
        except (ValueError, IndexError):
            await query.message.reply_text("⚠️ خطا در پردازش درخواست.")
            return
        added = fav_store.add(user_id, loc)
        msg = (
            f"✅ «{loc.display}» به علاقه‌مندی‌ها اضافه شد."
            if added
            else f"ℹ️ «{loc.display}» از قبل در علاقه‌مندی‌ها هست."
        )
        await query.message.reply_text(
            msg, reply_markup=back_to_menu_keyboard()
        )
        return

    # ── انتخاب شهر برای دریافت آب‌وهوا ────────────────────────────
    if data.startswith("city:"):
        try:
            parts = data.split(":")
            action = parts[1]
            loc = parse_callback_location(data)
        except (ValueError, IndexError):
            await query.message.reply_text("⚠️ خطا در پردازش درخواست.")
            return

        if action == "weather":
            await _reply_current_weather(query, loc)
        elif action == "forecast":
            await _reply_daily_forecast(query, loc)
        elif action == "hourly":
            await _reply_hourly_forecast(query, loc)
        elif action == "favadd":
            # کاربر روی یک شهر از لیست disambiguation کلیک کرده
            # تا آن را به علاقه‌مندی‌ها اضافه کند
            added = fav_store.add(user_id, loc)
            msg = (
                f"✅ «{loc.display}» به علاقه‌مندی‌ها اضافه شد."
                if added
                else f"ℹ️ «{loc.display}» از قبل در علاقه‌مندی‌ها هست."
            )
            await query.message.reply_text(
                msg, reply_markup=back_to_menu_keyboard()
            )
        else:
            await query.message.reply_text("⚠️ عملیات نامشخص.")
        return


# ─── توابع ارسال آب‌وهوا (مشترک بین دستور و callback) ─────────────────
async def _send_weather_for_city(
    update: Update, city_name: str
) -> None:
    single, candidates = await resolve_city(city_name, action="weather")
    if single is None and not candidates:
        await update.effective_message.reply_text(
            f"⚠️ شهری با نام «{city_name}» یافت نشد."
        )
        return
    if single is None:
        await update.effective_message.reply_text(
            f"چند شهر با نام «{city_name}» یافت شد. کدام منظور شماست؟",
            reply_markup=disambiguation_keyboard(candidates, "weather"),
        )
        return

    await update.effective_message.reply_text("🔄 در حال دریافت آب‌وهوا...")
    try:
        weather = await weather_client.get_weather(single)
    except WeatherAPIError as e:
        await send_error(update, str(e))
        return

    text = render_current_weather(single, weather)
    await update.effective_message.reply_text(
        text, reply_markup=city_action_keyboard(single)
    )


async def _send_forecast_for_city(
    update: Update, city_name: str
) -> None:
    single, candidates = await resolve_city(city_name, action="forecast")
    if single is None and not candidates:
        await update.effective_message.reply_text(
            f"⚠️ شهری با نام «{city_name}» یافت نشد."
        )
        return
    if single is None:
        await update.effective_message.reply_text(
            f"چند شهر با نام «{city_name}» یافت شد. کدام منظور شماست؟",
            reply_markup=disambiguation_keyboard(candidates, "forecast"),
        )
        return

    await update.effective_message.reply_text("🔄 در حال دریافت پیش‌بینی...")
    try:
        daily = await weather_client.get_daily_forecast(single)
    except WeatherAPIError as e:
        await send_error(update, str(e))
        return

    text = render_daily_forecast(single, daily)
    await update.effective_message.reply_text(
        text, reply_markup=back_to_menu_keyboard()
    )


async def _send_hourly_for_city(
    update: Update, city_name: str
) -> None:
    single, candidates = await resolve_city(city_name, action="hourly")
    if single is None and not candidates:
        await update.effective_message.reply_text(
            f"⚠️ شهری با نام «{city_name}» یافت نشد."
        )
        return
    if single is None:
        await update.effective_message.reply_text(
            f"چند شهر با نام «{city_name}» یافت شد. کدام منظور شماست؟",
            reply_markup=disambiguation_keyboard(candidates, "hourly"),
        )
        return

    await update.effective_message.reply_text("🔄 در حال دریافت پیش‌بینی...")
    try:
        hourly = await weather_client.get_hourly_forecast(single)
    except WeatherAPIError as e:
        await send_error(update, str(e))
        return

    text = render_hourly_forecast(single, hourly)
    await update.effective_message.reply_text(
        text, ParseMode.MARKDOWN, reply_markup=back_to_menu_keyboard()
    )


async def _reply_current_weather(query, loc: GeoLocation) -> None:
    await query.message.reply_text("🔄 در حال دریافت آب‌وهوا...")
    try:
        weather = await weather_client.get_weather(loc)
    except WeatherAPIError as e:
        await query.message.reply_text(f"⚠️ {e}")
        return
    text = render_current_weather(loc, weather)
    await query.message.reply_text(
        text, reply_markup=city_action_keyboard(loc)
    )


async def _reply_daily_forecast(query, loc: GeoLocation) -> None:
    await query.message.reply_text("🔄 در حال دریافت پیش‌بینی...")
    try:
        daily = await weather_client.get_daily_forecast(loc)
    except WeatherAPIError as e:
        await query.message.reply_text(f"⚠️ {e}")
        return
    text = render_daily_forecast(loc, daily)
    await query.message.reply_text(
        text, reply_markup=back_to_menu_keyboard()
    )


async def _reply_hourly_forecast(query, loc: GeoLocation) -> None:
    await query.message.reply_text("🔄 در حال دریافت پیش‌بینی...")
    try:
        hourly = await weather_client.get_hourly_forecast(loc)
    except WeatherAPIError as e:
        await query.message.reply_text(f"⚠️ {e}")
        return
    text = render_hourly_forecast(loc, hourly)
    await query.message.reply_text(
        text, ParseMode.MARKDOWN, reply_markup=back_to_menu_keyboard()
    )


# ─── مدیریت خطای سراسری ─────────────────────────────────────────────
async def error_handler(
    update: object, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """لاگ کردن خطاهای پیش‌بینی‌نشده."""
    logger.error(
        "Unhandled exception while handling update: %s",
        context.error, exc_info=context.error
    )
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ خطای پیش‌بینی‌نشده‌ای رخ داد. لطفاً دوباره تلاش کنید."
            )
        except Exception:
            pass


# ─── راه‌اندازی ربات ──────────────────────────────────────────────────
def build_application() -> Application:
    """ساخت و پیکربندی Application."""
    app = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .concurrent_updates(True)
        .build()
    )

    # دستورات
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("forecast", forecast_command))
    app.add_handler(CommandHandler("hourly", hourly_command))
    app.add_handler(CommandHandler("add", add_favorite_command))
    app.add_handler(CommandHandler("remove", remove_favorite_command))
    app.add_handler(CommandHandler("favorites", favorites_command))
    app.add_handler(CommandHandler("dev", dev_command))

    # موقعیت مکانی
    app.add_handler(
        MessageHandler(filters.LOCATION, location_handler)
    )

    # دکمه‌های شیشه‌ای
    app.add_handler(CallbackQueryHandler(callback_handler))

    # مدیریت خطا
    app.add_error_handler(error_handler)

    return app


def main() -> None:
    """نقطه ورودی."""
    logger.info("🚀 در حال راه‌اندازی ربات آب‌وهوا...")

    # بررسی توکن
    if not config.BOT_TOKEN or ":" not in config.BOT_TOKEN:
        logger.critical("❌ توکن ربات نامعتبر است.")
        sys.exit(1)

    # ── سازگاری با Python 3.14 ────────────────────────────────────
    # در Python 3.14 متد asyncio.get_event_loop() دیگر به‌صورت خودکار
    # یک event loop جدید نمی‌سازد و خطا می‌دهد. برای حل این مشکل،
    # خودمان یک event loop می‌سازیم و آن را به‌عنوان loop جاری تنظیم می‌کنیم.
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("loop closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app = build_application()
    logger.info("✅ ربات شروع به کار کرد. Ctrl+C برای توقف.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
