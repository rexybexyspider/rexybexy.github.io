"""
توابع کمکی برای قالب‌بندی پیام‌ها و ساخت کیبوردها.

این ماژول مسئول نمایش داده‌ها به فارسی روان و خوانا است.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from weather import (
    CurrentWeather,
    DailyForecast,
    GeoLocation,
    HourlyForecast,
    describe_weather,
)


# ─── توابع کمکی قالب‌بندی ─────────────────────────────────────────────
def format_temperature(temp: float) -> str:
    """قالب‌بندی دما با علامت درجه."""
    return f"{temp:+.1f}°"


def wind_direction_fa(degrees: int) -> str:
    """تبدیل زاویه باد به جهت فارسی."""
    directions = [
        "شمال", "شمال‌شرق", "شرق", "جنوب‌شرق",
        "جنوب", "جنوب‌غرب", "غرب", "شمال‌غرب",
    ]
    idx = round(degrees / 45) % 8
    return directions[idx]


def format_jalalian_date(iso_date: str) -> str:
    """
    تبدیل تاریخ میلادی ISO به تاریخ شمسی.
    نیازی به کتابخانه jdatetime نیست؛ با تقویم میلادی نمایش می‌دهیم
    و روز هفته را به فارسی برمی‌گردانیم.
    """
    try:
        dt = datetime.fromisoformat(iso_date)
    except ValueError:
        return iso_date

    weekdays_fa = [
        "دوشنبه", "سه‌شنبه", "چهارشنبه",
        "پنجشنبه", "جمعه", "شنبه", "یکشنبه",
    ]
    months_fa = [
        "ژانویه", "فوریه", "مارس", "آوریل", "مه", "ژوئن",
        "ژوئیه", "اوت", "سپتامبر", "اکتبر", "نوامبر", "دسامبر",
    ]
    weekday = weekdays_fa[dt.weekday()]
    month = months_fa[dt.month - 1]
    return f"{weekday}، {dt.day} {month}"


def format_time_only(iso_time: str) -> str:
    """استخراج فقط ساعت و دقیقه از ISO time."""
    try:
        dt = datetime.fromisoformat(iso_time)
        return dt.strftime("%H:%M")
    except ValueError:
        return iso_time


# ─── قالب‌بندی پیام‌ها ────────────────────────────────────────────────
def render_current_weather(
    location: GeoLocation, weather: CurrentWeather
) -> str:
    """قالب‌بندی پیام آب‌وهوای فعلی."""
    day_part = "روز ☀️" if weather.is_day else "شب 🌙"
    lines = [
        f"📍 {location.display}",
        f"🌤 وضعیت: {weather.emoji} {weather.description}",
        f"🌡 دما: {format_temperature(weather.temperature)}",
        f"🤔 دمای محسوس: {format_temperature(weather.apparent_temperature)}",
        f"💧 رطوبت: {weather.humidity}٪",
        f"💨 باد: {weather.wind_speed:.1f} km/h "
        f"({wind_direction_fa(weather.wind_direction)})",
        f"🌧 بارش: {weather.precipitation:.1f} mm",
        f"🌓 زمان: {day_part}",
    ]
    return "\n".join(lines)


def render_daily_forecast(
    location: GeoLocation, forecast: Iterable[DailyForecast]
) -> str:
    """قالب‌بندی پیام پیش‌بینی روزانه."""
    lines = [f"📅 پیش‌بینی ۳ روزه — {location.display}", ""]
    for f in forecast:
        lines.extend(
            [
                f"━━━━━━━━━━━━━━━",
                f"{f.emoji} {format_jalalian_date(f.date)}",
                f"   وضعیت: {f.description}",
                f"   🌡 دما: {f.temp_min:+.0f}° تا {f.temp_max:+.0f}°",
                f"   🌧 بارش: {f.precipitation:.1f} mm",
                f"   💸 باد: تا {f.wind_speed_max:.1f} km/h",
                f"   🌅 طلوع: {format_time_only(f.sunrise)} | "
                f"🌅 غروب: {format_time_only(f.sunset)}",
            ]
        )
    return "\n".join(lines)


def render_hourly_forecast(
    location: GeoLocation, forecast: Iterable[HourlyForecast]
) -> str:
    """
    قالب‌بندی پیام پیش‌بینی ساعتی به‌صورت جدول متنی هم‌تراز.
    ستون‌های عددی (ساعت، دما، بارش) با padding دقیق تراز می‌شوند
    و ایموجی وضعیت در انتهای هر ردیف قرار می‌گیرد تا اختلال تراز
    ایجاد نکند. هدر جدول با حروف لاتین نوشته شده تا با اعداد لاتین
    بدنه دقیقاً هم‌تراز بماند (در فونت monospace تلگرام).
    """
    lines = [f"⏰ پیش‌بینی ۲۴ ساعت آینده — {location.display}", ""]

    # راهنمای ستون‌ها (خارج از بلاک کد، با فارسی روان)
    lines.append("📊 ترتیب ستون‌ها: ساعت | دما | احتمال بارش | وضعیت")
    lines.append("")

    # جدول داخل بلاک کد برای تراز monospace
    lines.append("```")
    # هدر با حروف لاتین برای تراز دقیق با اعداد لاتین بدنه
    lines.append(" Hour │  Temp  │ Rain │ W")
    lines.append(" ────┼────────┼──────┼───")
    for h in forecast:
        time_str = format_time_only(h.time)
        # دما با یک رقم اعشار برای ثبات عرض
        temp = f"{h.temperature:+.1f}°"
        # احتمال بارش با padding راست برای تراز عددی
        prob = f"{h.precipitation_probability:>2d}%"
        lines.append(f" {time_str} │ {temp:<6} │ {prob:<4} │ {h.emoji}")
    lines.append("```")
    return "\n".join(lines)


def render_favorites(favorites: list[GeoLocation]) -> str:
    """قالب‌بندی لیست علاقه‌مندی‌ها."""
    if not favorites:
        return (
            "⭐ لیست علاقه‌مندی‌های شما خالی است.\n\n"
            "برای افزودن شهر از دستور زیر استفاده کنید:\n"
            "/add <نام شهر>\n"
            "مثال: /add تهران"
        )
    lines = ["⭐ شهرهای موردعلاقه شما:", ""]
    for i, loc in enumerate(favorites, 1):
        lines.append(f"{i}. {loc.display}")
    lines.extend(
        [
            "",
            "💡 برای مشاهده آب‌وهوا روی دکمه شهر مورد نظر بزنید.",
            "برای حذف: /remove <نام شهر>",
        ]
    )
    return "\n".join(lines)


# ─── کیبوردها ─────────────────────────────────────────────────────────
def main_menu_keyboard() -> InlineKeyboardMarkup:
    """منوی اصلی ربات."""
    keyboard = [
        [
            InlineKeyboardButton("🌤 آب‌وهوای فعلی", callback_data="weather"),
            InlineKeyboardButton("📅 ۳ روزه", callback_data="forecast"),
        ],
        [
            InlineKeyboardButton("⏰ ساعتی", callback_data="hourly"),
            InlineKeyboardButton("⭐ علاقه‌مندی‌ها", callback_data="favorites"),
        ],
        [InlineKeyboardButton("📖 راهنما", callback_data="help")],
    ]
    return InlineKeyboardMarkup(keyboard)


def favorite_cities_keyboard(
    user_id: int, action: str = "weather"
) -> InlineKeyboardMarkup:
    """
    کیبورد انتخاب شهر از علاقه‌مندی‌ها.
    action: 'weather' | 'forecast' | 'hourly' | 'remove'
    """
    from storage import favorites as fav_store

    cities = fav_store.list(user_id)
    if not cities:
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton("↩️ بازگشت", callback_data="menu")]]
        )

    rows = []
    for city in cities:
        label = city.name or city.name_en
        rows.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"city:{action}:{city.name_en}:{city.latitude:.4f},{city.longitude:.4f}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("↩️ بازگشت", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def city_action_keyboard(location: GeoLocation) -> InlineKeyboardMarkup:
    """کیبورد عملیات روی یک شهر پس از نمایش آب‌وهوا."""
    coord = f"{location.latitude:.4f},{location.longitude:.4f}"
    name = location.name_en
    keyboard = [
        [
            InlineKeyboardButton(
                "📅 پیش‌بینی ۳ روزه",
                callback_data=f"city:forecast:{name}:{coord}",
            ),
            InlineKeyboardButton(
                "⏰ پیش‌بینی ساعتی",
                callback_data=f"city:hourly:{name}:{coord}",
            ),
        ],
        [
            InlineKeyboardButton(
                "⭐ افزودن به علاقه‌مندی",
                callback_data=f"favadd:{name}:{coord}",
            ),
        ],
        [InlineKeyboardButton("↩️ منوی اصلی", callback_data="menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("↩️ منوی اصلی", callback_data="menu")]]
    )


def disambiguation_keyboard(
    locations: list[GeoLocation], action: str = "weather"
) -> InlineKeyboardMarkup:
    """
    کیبورد انتخاب شهر هنگام ambiguity جستجو.
    """
    rows = []
    for loc in locations:
        coord = f"{loc.latitude:.4f},{loc.longitude:.4f}"
        rows.append(
            [
                InlineKeyboardButton(
                    loc.display,
                    callback_data=f"city:{action}:{loc.name_en}:{coord}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("↩️ لغو", callback_data="menu")])
    return InlineKeyboardMarkup(rows)
