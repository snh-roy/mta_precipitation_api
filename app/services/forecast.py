import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.config import get_settings


class ForecastService:
    """Service for fetching NWS gridpoint forecast precipitation."""

    _duration_re = re.compile(
        r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?)?$"
    )

    def __init__(self):
        self.settings = get_settings()
        self._points_cache: dict[str, dict] = {}
        self._grid_cache: dict[str, dict] = {}
        self._cache_time: dict[str, datetime] = {}
        self._cache_ttl = timedelta(minutes=30)

    def _cache_key_for_point(self, lat: float, lon: float) -> str:
        return f"{round(lat, 3)},{round(lon, 3)}"

    def _is_cache_valid(self, key: str) -> bool:
        cached_at = self._cache_time.get(key)
        if not cached_at:
            return False
        return datetime.now(timezone.utc) - cached_at < self._cache_ttl

    def _parse_duration_hours(self, duration: str) -> float:
        match = self._duration_re.match(duration)
        if not match:
            return 0.0
        days = int(match.group("days") or 0)
        hours = int(match.group("hours") or 0)
        minutes = int(match.group("minutes") or 0)
        return days * 24 + hours + minutes / 60.0

    def _parse_valid_time(self, valid_time: str) -> tuple[datetime, float]:
        # Example: "2026-01-25T14:00:00+00:00/PT1H"
        if "/" not in valid_time:
            return datetime.now(timezone.utc), 0.0
        start_str, duration_str = valid_time.split("/", 1)
        start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        hours = self._parse_duration_hours(duration_str)
        return start, hours

    async def _fetch_points(self, lat: float, lon: float) -> Optional[dict]:
        key = self._cache_key_for_point(lat, lon)
        if key in self._points_cache and self._is_cache_valid(key):
            return self._points_cache[key]

        url = f"{self.settings.nws_base_url}/points/{lat},{lon}"
        headers = {"User-Agent": "mta-flood-api"}

        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(url, headers=headers, timeout=15.0)
                response.raise_for_status()
                data = response.json()
                self._points_cache[key] = data
                self._cache_time[key] = datetime.now(timezone.utc)
                return data
        except Exception as e:
            print(f"Error fetching NWS points for {lat},{lon}: {e}")
            return None

    async def _fetch_grid(self, grid_url: str) -> Optional[dict]:
        if grid_url in self._grid_cache and self._is_cache_valid(grid_url):
            return self._grid_cache[grid_url]

        headers = {"User-Agent": "mta-flood-api"}
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(grid_url, headers=headers, timeout=15.0)
                response.raise_for_status()
                data = response.json()
                self._grid_cache[grid_url] = data
                self._cache_time[grid_url] = datetime.now(timezone.utc)
                return data
        except Exception as e:
            print(f"Error fetching NWS grid data: {e}")
            return None

    async def get_forecast_totals(
        self, lat: float, lon: float
    ) -> tuple[Optional[float], Optional[float], Optional[str]]:
        """
        Return (next_6hr_total_in, next_24hr_total_in) from NWS gridpoint data.
        """
        points = await self._fetch_points(lat, lon)
        if not points:
            return None, None, None

        grid_url = points.get("properties", {}).get("forecastGridData")
        if not grid_url:
            return None, None, None

        grid = await self._fetch_grid(grid_url)
        if not grid:
            return None, None, None

        qpf = grid.get("properties", {}).get("quantitativePrecipitation", {})
        values = qpf.get("values", [])
        if not values:
            return None, None, grid_url

        now = datetime.now(timezone.utc)
        total_6h_mm = 0.0
        total_24h_mm = 0.0

        for entry in values:
            valid_time = entry.get("validTime")
            value_mm = entry.get("value")
            if valid_time is None or value_mm is None:
                continue

            start, hours = self._parse_valid_time(valid_time)
            if hours <= 0:
                continue

            # Skip past periods
            if start + timedelta(hours=hours) <= now:
                continue

            # Portion overlap with next 6h and 24h windows
            window_6_end = now + timedelta(hours=6)
            window_24_end = now + timedelta(hours=24)

            period_end = start + timedelta(hours=hours)
            overlap_6 = max(
                0.0,
                (min(period_end, window_6_end) - max(start, now)).total_seconds() / 3600.0,
            )
            overlap_24 = max(
                0.0,
                (min(period_end, window_24_end) - max(start, now)).total_seconds() / 3600.0,
            )

            if overlap_6 > 0:
                total_6h_mm += value_mm * (overlap_6 / hours)
            if overlap_24 > 0:
                total_24h_mm += value_mm * (overlap_24 / hours)

        # Convert mm to inches
        return total_6h_mm / 25.4, total_24h_mm / 25.4, grid_url


forecast_service = ForecastService()
