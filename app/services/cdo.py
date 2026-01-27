from datetime import datetime
from typing import Optional

import httpx

from app.config import get_settings


class CDOService:
    """Service for fetching daily precipitation totals from NCEI CDO (GHCN-Daily)."""

    def __init__(self):
        self.settings = get_settings()

    def _build_headers(self) -> dict:
        token = self.settings.ncei_cdo_token
        return {"token": token} if token else {}

    async def _fetch_station_daily_precip(
        self, station_id: str, report_date: str
    ) -> Optional[float]:
        """
        Fetch daily precipitation total for a station on a given date.

        Returns inches if CDO is configured for standard units.
        """
        params = {
            "datasetid": "GHCND",
            "datatypeid": "PRCP",
            "stationid": station_id,
            "startdate": report_date,
            "enddate": report_date,
            "units": "standard",
            "limit": 1000,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.settings.ncei_cdo_base_url,
                    params=params,
                    headers=self._build_headers(),
                    timeout=15.0,
                )
                response.raise_for_status()
                data = response.json()

            results = data.get("results", [])
            if not results:
                return None

            # GHCN-Daily PRCP in standard units is expected to be inches.
            value = results[0].get("value")
            if value is None:
                return None

            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        except Exception as e:
            print(f"Error fetching CDO data for {station_id}: {e}")
            return None

    async def get_daily_precip_totals(self, report_date: str) -> dict[str, Optional[float]]:
        """Fetch daily precipitation totals for Central Park, JFK, and LaGuardia."""
        settings = self.settings
        cp = await self._fetch_station_daily_precip(settings.ghcnd_central_park_station, report_date)
        jfk = await self._fetch_station_daily_precip(settings.ghcnd_jfk_station, report_date)
        lga = await self._fetch_station_daily_precip(settings.ghcnd_lga_station, report_date)

        return {
            "central_park_daily_in": cp,
            "jfk_daily_in": jfk,
            "lga_daily_in": lga,
        }

    async def is_available(self) -> bool:
        """Check if CDO is available."""
        try:
            params = {
                "datasetid": "GHCND",
                "datatypeid": "PRCP",
                "stationid": self.settings.ghcnd_central_park_station,
                "startdate": "2026-01-20",
                "enddate": "2026-01-20",
                "units": "standard",
                "limit": 1,
            }
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.settings.ncei_cdo_base_url,
                    params=params,
                    headers=self._build_headers(),
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception:
            return False


cdo_service = CDOService()
