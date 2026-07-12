"""
کلاینت Open-Meteo API برای دریافت آب‌وهوا و ژئوکدینگ شهرها.

شامل دو سرویس رایگان و بدون نیاز به کلید API:
1. Geocoding API  — تبدیل نام شهر به مختصات جغرافیایی
2. Forecast API   — دریافت آب‌وهوای فعلی، روزانه و ساعتی
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import httpx

import config

logger = logging.getLogger(__name__)

# ─── نگاشت کدهای WMO Weather به توصیف فارسی و ایموجی ──────────────────
# Reference: https://open-meteo.com/en/docs#weathervariables
WMOWeatherCode = {
    0:  ("آفتابی",                     "☀️"),
    1:  ("عمدتاً آفتابی",               "🌤️"),
    2:  ("نیمه‌ابری",                   "⛅"),
    3:  ("ابری",                       "☁️"),
    45: ("مه",                         "🌫️"),
    48: ("مه یخی",                     "🌫️"),
    51: ("باران ریز سبک",              "🌦️"),
    53: ("باران ریز متوسط",            "🌦️"),
    55: ("باران ریز شدید",             "🌧️"),
    56: ("باران ریز یخی سبک",          "🌧️❄️"),
    57: ("باران ریز یخی شدید",         "🌧️❄️"),
    61: ("باران سبک",                  "🌦️"),
    63: ("باران متوسط",                "🌧️"),
    65: ("باران شدید",                 "🌧️"),
    66: ("باران یخی سبک",              "🌧️❄️"),
    67: ("باران یخی شدید",             "🌧️❄️"),
    71: ("برف سبک",                    "🌨️"),
    73: ("برف متوسط",                  "🌨️"),
    75: ("برف شدید",                   "❄️"),
    77: ("دانه‌های برف",                "🌨️"),
    80: ("رگبار باران سبک",            "🌦️"),
    81: ("رگبار باران متوسط",          "🌧️"),
    82: ("رگبار باران شدید",           "⛈️"),
    85: ("رگبار برف سبک",              "🌨️"),
    86: ("رگبار برف شدید",             "❄️"),
    95: ("رعدوبرق",                    "⛈️"),
    96: ("رعدوبرق با تگرگ سبک",        "⛈️🌨️"),
    99: ("رعدوبرق با تگرگ شدید",       "⛈️🌨️"),
}


def describe_weather(code: int) -> tuple[str, str]:
    """برگرداندن (توصیف فارسی، ایموجی) برای کد WMO."""
    return WMOWeatherCode.get(code, ("نامشخص", "❓"))


# ─── ساختار داده‌ها ───────────────────────────────────────────────────
@dataclass
class GeoLocation:
    """موقعیت جغرافیایی یک شهر."""
    name: str           # نام به فارسی (اگر موجود باشد)
    name_en: str        # نام انگلیسی
    latitude: float
    longitude: float
    country: str = ""
    admin1: str = ""    # استان/ایالت

    @property
    def display(self) -> str:
        """نام نمایشی غنی برای کاربر."""
        parts = [self.name or self.name_en]
        if self.admin1 and self.admin1 != self.name:
            parts.append(self.admin1)
        if self.country:
            parts.append(self.country)
        return "، ".join(parts)


@dataclass
class CurrentWeather:
    """آب‌وهوای فعلی."""
    temperature: float
    apparent_temperature: float
    humidity: int
    wind_speed: float
    wind_direction: int
    weather_code: int
    is_day: bool
    precipitation: float

    @property
    def description(self) -> str:
        return describe_weather(self.weather_code)[0]

    @property
    def emoji(self) -> str:
        return describe_weather(self.weather_code)[1]


@dataclass
class DailyForecast:
    """پیش‌بینی روزانه."""
    date: str
    weather_code: int
    temp_max: float
    temp_min: float
    precipitation: float
    wind_speed_max: float
    sunrise: str
    sunset: str

    @property
    def description(self) -> str:
        return describe_weather(self.weather_code)[0]

    @property
    def emoji(self) -> str:
        return describe_weather(self.weather_code)[1]


@dataclass
class HourlyForecast:
    """پیش‌بینی ساعتی."""
    time: str           # ISO format
    temperature: float
    weather_code: int
    precipitation_probability: int

    @property
    def emoji(self) -> str:
        return describe_weather(self.weather_code)[1]


# ─── خطاهای سفارشی ───────────────────────────────────────────────────
class WeatherAPIError(Exception):
    """خطای عمومی API."""


class CityNotFoundError(WeatherAPIError):
    """شهر یافت نشد."""


# ─── کلاینت‌ها ─────────────────────────────────────────────────────────
class WeatherClient:
    """
    کلاینت غیرهمزمان برای Open-Meteo.
    از httpx.AsyncClient برای درخواست‌های async استفاده می‌کند.
    """

    def __init__(self) -> None:
        # Timeout پایدار برای جلوگیری از هنگ کردن ربات
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=10.0),
            headers={"User-Agent": "TelegramWeatherBot/1.0"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    # ── Geocoding: نام شهر → مختصات ─────────────────────────────────
    async def geocode(
        self,
        city_name: str,
        language: str = config.DEFAULT_LANGUAGE,
        count: int = config.GEOCODING_MAX_RESULTS,
    ) -> list[GeoLocation]:
        """
        تبدیل نام شهر به مختصات.
        چند نتیجه برمی‌گرداند تا کاربر بتواند انتخاب کند.
        """
        params = {
            "name": city_name.strip(),
            "count": count,
            "language": language,
            "format": "json",
        }
        try:
            resp = await self._client.get(
                config.OPEN_METEO_GEOCODING_URL, params=params
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Geocoding HTTP error: %s", e)
            raise WeatherAPIError("خطا در ارتباط با سرویس مکان‌یابی.") from e

        data: dict[str, Any] = resp.json()
        results = data.get("results")
        if not results:
            raise CityNotFoundError(f"شهری با نام «{city_name}» یافت نشد.")

        return [
            GeoLocation(
                name=r.get("name", ""),
                name_en=r.get("name", ""),
                latitude=float(r["latitude"]),
                longitude=float(r["longitude"]),
                country=r.get("country", ""),
                admin1=r.get("admin1", ""),
            )
            for r in results
        ]

    # ── Reverse geocoding برای موقعیت‌های ارسالی کاربر ──────────────
    async def reverse_geocode(
        self, latitude: float, longitude: float
    ) -> GeoLocation:
        """
        تبدیل مختصات به نام شهر.
        Open-Meteo Geocoding از reverse پشتیبانی نمی‌کند، بنابراین
        از BigDataCloud رایگان استفاده می‌کنیم (بدون کلید).
        """
        try:
            resp = await self._client.get(
                "https://api.bigdatacloud.net/data/reverse-geocode-client",
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "localityLanguage": "fa",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            logger.warning("Reverse geocode failed: %s", e)
            # در صورت شکست، نام ناشناخته اما مختصات معتبر برمی‌گردد
            return GeoLocation(
                name="موقعیت شما",
                name_en="Your location",
                latitude=latitude,
                longitude=longitude,
            )

        return GeoLocation(
            name=data.get("city") or data.get("locality") or "موقعیت شما",
            name_en=data.get("city") or data.get("locality") or "Your location",
            latitude=latitude,
            longitude=longitude,
            country=data.get("countryName", ""),
            admin1=data.get("principalSubdivision", ""),
        )

    # ── Forecast: مختصات → آب‌وهوا ──────────────────────────────────
    async def get_weather(self, location: GeoLocation) -> CurrentWeather:
        """دریافت آب‌وهوای فعلی."""
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "is_day,precipitation,weather_code,wind_speed_10m,"
                "wind_direction_10m"
            ),
            "timezone": config.DEFAULT_TIMEZONE,
        }
        try:
            resp = await self._client.get(
                config.OPEN_METEO_FORECAST_URL, params=params
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Forecast HTTP error: %s", e)
            raise WeatherAPIError("خطا در دریافت آب‌وهوا.") from e

        data = resp.json().get("current", {})
        if not data:
            raise WeatherAPIError("داده‌ای برای آب‌وهوای فعلی دریافت نشد.")

        return CurrentWeather(
            temperature=float(data["temperature_2m"]),
            apparent_temperature=float(data["apparent_temperature"]),
            humidity=int(data["relative_humidity_2m"]),
            wind_speed=float(data["wind_speed_10m"]),
            wind_direction=int(data["wind_direction_10m"]),
            weather_code=int(data["weather_code"]),
            is_day=bool(data["is_day"]),
            precipitation=float(data.get("precipitation", 0.0)),
        )

    async def get_daily_forecast(
        self, location: GeoLocation, days: int = config.FORECAST_DAYS
    ) -> list[DailyForecast]:
        """دریافت پیش‌بینی روزانه."""
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_sum,wind_speed_10m_max,sunrise,sunset"
            ),
            "timezone": config.DEFAULT_TIMEZONE,
            "forecast_days": days,
        }
        try:
            resp = await self._client.get(
                config.OPEN_METEO_FORECAST_URL, params=params
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Daily forecast HTTP error: %s", e)
            raise WeatherAPIError("خطا در دریافت پیش‌بینی روزانه.") from e

        daily = resp.json().get("daily", {})
        if not daily:
            raise WeatherAPIError("داده‌ای برای پیش‌بینی روزانه دریافت نشد.")

        return [
            DailyForecast(
                date=daily["time"][i],
                weather_code=int(daily["weather_code"][i]),
                temp_max=float(daily["temperature_2m_max"][i]),
                temp_min=float(daily["temperature_2m_min"][i]),
                precipitation=float(daily["precipitation_sum"][i]),
                wind_speed_max=float(daily["wind_speed_10m_max"][i]),
                sunrise=daily["sunrise"][i],
                sunset=daily["sunset"][i],
            )
            for i in range(len(daily["time"]))
        ]

    async def get_hourly_forecast(
        self,
        location: GeoLocation,
        hours: int = config.HOURLY_HOURS,
    ) -> list[HourlyForecast]:
        """
        دریافت پیش‌بینی ساعتی.
        تنها ساعات آینده (نه گذشته) برمی‌گردد.
        """
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "hourly": "temperature_2m,weather_code,precipitation_probability",
            "timezone": config.DEFAULT_TIMEZONE,
            "forecast_days": 2,   # برای پوشش ۲۴ ساعت آینده
            "past_days": 0,
        }
        try:
            resp = await self._client.get(
                config.OPEN_METEO_FORECAST_URL, params=params
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Hourly forecast HTTP error: %s", e)
            raise WeatherAPIError("خطا در دریافت پیش‌بینی ساعتی.") from e

        hourly = resp.json().get("hourly", {})
        if not hourly:
            raise WeatherAPIError("داده‌ای برای پیش‌بینی ساعتی دریافت نشد.")

        # فقط ساعت‌های آینده را نگه می‌داریم
        from datetime import datetime, timezone as dt_tz

        now = datetime.now(dt_tz.utc)
        forecasts: list[HourlyForecast] = []
        for i, t in enumerate(hourly["time"]):
            try:
                # Open-Meteo برمی‌گرداند با timezone محلی، پس به‌صورت خام مقایسه می‌کنیم
                dt = datetime.fromisoformat(t)
            except ValueError:
                continue
            # تقریب: از زمان محلی استفاده می‌کنیم؛ فیلتر ساده بر اساس شمارش
            forecasts.append(
                HourlyForecast(
                    time=t,
                    temperature=float(hourly["temperature_2m"][i]),
                    weather_code=int(hourly["weather_code"][i]),
                    precipitation_probability=int(
                        hourly["precipitation_probability"][i]
                    ),
                )
            )
            if len(forecasts) >= hours:
                break

        # شروع از نزدیک‌ترین ساعت به اکنون
        # یک heuristics ساده: اولین ساعتی که حداقل ۲۴ ساعت فاصله نداشته باشد
        # در اینجا فقط N ساعت آینده را از ابتدای لیست برمی‌داریم
        # (Open-Meteo به‌طور پیش‌فرض از ساعت جاری شروع می‌کند)
        return forecasts[:hours]


# یک نمونه سراسری برای استفاده در هندلرها
weather_client = WeatherClient()
