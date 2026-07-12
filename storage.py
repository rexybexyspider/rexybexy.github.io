"""
ذخیره‌سازی شهرهای موردعلاقه هر کاربر در فایل JSON.

ساختار داده:
{
  "user_id": [
    {"name": "تهران", "name_en": "Tehran", "latitude": 35.69, "longitude": 51.39, "country": "Iran", "admin1": "Tehran"},
    ...
  ]
}
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Optional

from weather import GeoLocation

import config

logger = logging.getLogger(__name__)


class FavoritesStorage:
    """مدیریت شهرهای موردعلاقه کاربران با ذخیره JSON."""

    def __init__(self, file_path: Path = config.FAVORITES_FILE) -> None:
        self._file = file_path
        self._lock = threading.Lock()
        self._cache: dict[str, list[dict]] = {}
        self._load()

    # ── بارگذاری و ذخیره ─────────────────────────────────────────────
    def _load(self) -> None:
        if not self._file.exists():
            self._cache = {}
            return
        try:
            self._cache = json.loads(self._file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load favorites: %s", e)
            self._cache = {}

    def _save(self) -> None:
        try:
            self._file.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error("Failed to save favorites: %s", e)

    # ── عملیات ────────────────────────────────────────────────────────
    def add(self, user_id: int, location: GeoLocation) -> bool:
        """
        افزودن شهر به علاقه‌مندی‌ها.
        برمی‌گرداند: True اگر اضافه شد، False اگر قبلاً وجود داشت.
        """
        key = str(user_id)
        with self._lock:
            favorites = self._cache.setdefault(key, [])
            # چک کردن تکراری بودن با مختصات
            for f in favorites:
                if (
                    abs(f["latitude"] - location.latitude) < 0.01
                    and abs(f["longitude"] - location.longitude) < 0.01
                ):
                    return False
            favorites.append(
                {
                    "name": location.name,
                    "name_en": location.name_en,
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                    "country": location.country,
                    "admin1": location.admin1,
                }
            )
            self._save()
            return True

    def remove(self, user_id: int, name: str) -> bool:
        """
        حذف شهر با نام.
        برمی‌گرداند: True اگر حذف شد، False اگر پیدا نشد.
        """
        key = str(user_id)
        name_lower = name.strip().lower()
        with self._lock:
            favorites = self._cache.get(key, [])
            before = len(favorites)
            favorites = [
                f for f in favorites
                if f.get("name", "").lower() != name_lower
                and f.get("name_en", "").lower() != name_lower
            ]
            if len(favorites) == before:
                return False
            self._cache[key] = favorites
            self._save()
            return True

    def list(self, user_id: int) -> list[GeoLocation]:
        """برگرداندن لیست علاقه‌مندی‌های کاربر."""
        items = self._cache.get(str(user_id), [])
        return [
            GeoLocation(
                name=i["name"],
                name_en=i.get("name_en", i["name"]),
                latitude=i["latitude"],
                longitude=i["longitude"],
                country=i.get("country", ""),
                admin1=i.get("admin1", ""),
            )
            for i in items
        ]

    def get_by_name(
        self, user_id: int, name: str
    ) -> Optional[GeoLocation]:
        """یافتن شهر از علاقه‌مندی‌ها با نام."""
        name_lower = name.strip().lower()
        for loc in self.list(user_id):
            if (
                loc.name.lower() == name_lower
                or loc.name_en.lower() == name_lower
            ):
                return loc
        return None


# نمونه سراسری
favorites = FavoritesStorage()
