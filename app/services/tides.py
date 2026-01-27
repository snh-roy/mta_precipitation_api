from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.config import get_settings
from app.models import TideReading


class TidesService:
    """Service for fetching tide/water level data from NOAA and USGS."""

    NOAA_STATIONS = {
        "8518750": "The Battery, NY",
        "8516945": "Kings Point, NY",
    }

    def __init__(self):
        self.settings = get_settings()
        self._tide_cache: dict[str, TideReading] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=6)  # NOAA updates every 6 minutes

    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid."""
        if self._cache_time is None:
            return False
        return datetime.now(timezone.utc) - self._cache_time < self._cache_ttl

    async def fetch_noaa_tide(self, station_id: str) -> Optional[TideReading]:
        """Fetch water level from a NOAA tide station."""
        params = {
            "station": station_id,
            "product": "water_level",
            "datum": "MLLW",
            "units": "english",
            "time_zone": "gmt",
            "application": "mta_flood_api",
            "format": "json",
            "date": "latest",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.settings.noaa_tides_base_url,
                    params=params,
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                if "data" not in data or len(data["data"]) == 0:
                    return None

                reading = data["data"][0]
                water_level = float(reading["v"])
                timestamp_str = reading["t"]

                # Parse NOAA timestamp format: "2026-01-23 14:30"
                timestamp = datetime.strptime(
                    timestamp_str, "%Y-%m-%d %H:%M"
                ).replace(tzinfo=timezone.utc)

                return TideReading(
                    station_id=station_id,
                    station_name=self.NOAA_STATIONS.get(station_id, station_id),
                    water_level_ft=water_level,
                    timestamp=timestamp,
                    datum="MLLW",
                )

        except Exception as e:
            print(f"Error fetching NOAA tide data for {station_id}: {e}")
            return None

    async def fetch_usgs_water_levels(self) -> list[dict]:
        """Fetch water level data from USGS."""
        params = {
            "sites": self.settings.usgs_sites,
            "parameterCd": "00065",  # Gage height
            "format": "json",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.settings.usgs_water_url,
                    params=params,
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                results = []
                time_series = data.get("value", {}).get("timeSeries", [])

                for ts in time_series:
                    site_code = ts.get("sourceInfo", {}).get("siteCode", [{}])[0].get("value")
                    site_name = ts.get("sourceInfo", {}).get("siteName", "Unknown")
                    values = ts.get("values", [{}])[0].get("value", [])

                    if values:
                        latest = values[-1]
                        results.append({
                            "site_id": site_code,
                            "site_name": site_name,
                            "water_level_ft": float(latest.get("value", 0)),
                            "timestamp": latest.get("dateTime"),
                        })

                return results

        except Exception as e:
            print(f"Error fetching USGS water data: {e}")
            return []

    async def get_all_tide_readings(
        self, force_refresh: bool = False
    ) -> list[TideReading]:
        """Get all tide readings from NOAA stations."""
        if not force_refresh and self._is_cache_valid():
            return list(self._tide_cache.values())

        readings = []

        # Fetch from both NOAA stations
        for station_id in self.NOAA_STATIONS.keys():
            reading = await self.fetch_noaa_tide(station_id)
            if reading:
                readings.append(reading)
                self._tide_cache[station_id] = reading

        self._cache_time = datetime.now(timezone.utc)
        return readings

    async def get_current_tide_level(self) -> Optional[float]:
        """Get the current tide level (average of available stations)."""
        readings = await self.get_all_tide_readings()

        if not readings:
            return None

        return sum(r.water_level_ft for r in readings) / len(readings)

    async def get_battery_tide_level(self) -> Optional[float]:
        """Get tide level specifically from The Battery station."""
        if self._is_cache_valid() and "8518750" in self._tide_cache:
            return self._tide_cache["8518750"].water_level_ft

        reading = await self.fetch_noaa_tide(self.settings.noaa_battery_station)
        if reading:
            self._tide_cache["8518750"] = reading
            return reading.water_level_ft

        return None

    async def is_available(self) -> bool:
        """Check if tide data is available."""
        try:
            reading = await self.fetch_noaa_tide(self.settings.noaa_battery_station)
            return reading is not None
        except Exception:
            return False


tides_service = TidesService()
