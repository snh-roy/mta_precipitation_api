import os
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd

from app.config import COASTAL_STATIONS, get_settings


class StationsService:
    """Service for loading and managing MTA station data."""

    def __init__(self):
        self.settings = get_settings()
        self._stations_df: Optional[pd.DataFrame] = None

    async def load_stations(self, force_refresh: bool = False) -> pd.DataFrame:
        """Load MTA stations from cache or download from MTA."""
        cache_path = Path(self.settings.stations_cache_path)

        if not force_refresh and cache_path.exists():
            return self._load_from_cache(cache_path)

        return await self._download_and_cache(cache_path)

    def _load_from_cache(self, cache_path: Path) -> pd.DataFrame:
        """Load stations from local cache."""
        df = pd.read_csv(cache_path)
        self._stations_df = self._normalize_dataframe(df)
        return self._stations_df

    async def _download_and_cache(self, cache_path: Path) -> pd.DataFrame:
        """Download stations from MTA and cache locally."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.settings.mta_stations_url,
                timeout=30.0
            )
            response.raise_for_status()

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(response.text)

        df = pd.read_csv(cache_path)
        self._stations_df = self._normalize_dataframe(df)
        return self._stations_df

    def _normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names and add computed fields."""
        column_mapping = {
            "Station ID": "station_id",
            "Complex ID": "complex_id",
            "GTFS Stop ID": "gtfs_stop_id",
            "Division": "division",
            "Line": "line",
            "Stop Name": "station_name",
            "Borough": "borough",
            "Daytime Routes": "daytime_routes",
            "Structure": "structure",
            "GTFS Latitude": "latitude",
            "GTFS Longitude": "longitude",
            "North Direction Label": "north_label",
            "South Direction Label": "south_label",
        }

        df = df.rename(columns=column_mapping)

        available_cols = [col for col in column_mapping.values() if col in df.columns]
        df = df[available_cols].copy()

        df["station_id"] = df["station_id"].astype(str)

        df["is_coastal"] = df["station_name"].apply(
            lambda x: x in COASTAL_STATIONS if pd.notna(x) else False
        )

        df = df.drop_duplicates(subset=["station_name", "borough"], keep="first")

        return df

    async def get_stations(self, borough: Optional[str] = None) -> pd.DataFrame:
        """Get stations, optionally filtered by borough."""
        if self._stations_df is None:
            await self.load_stations()

        df = self._stations_df.copy()

        if borough:
            borough_map = {
                "M": "Manhattan",
                "Bk": "Brooklyn",
                "Q": "Queens",
                "Bx": "Bronx",
                "SI": "Staten Island",
            }
            df["borough_full"] = df["borough"].map(borough_map).fillna(df["borough"])
            df = df[df["borough_full"].str.lower() == borough.lower()]
            df = df.drop(columns=["borough_full"])

        return df

    async def get_station_by_name(self, station_name: str) -> Optional[dict]:
        """Get a single station by name."""
        if self._stations_df is None:
            await self.load_stations()

        matches = self._stations_df[
            self._stations_df["station_name"].str.lower() == station_name.lower()
        ]

        if matches.empty:
            matches = self._stations_df[
                self._stations_df["station_name"].str.lower().str.contains(
                    station_name.lower(), regex=False
                )
            ]

        if matches.empty:
            return None

        return matches.iloc[0].to_dict()

    async def get_coastal_stations(self) -> pd.DataFrame:
        """Get only coastal stations."""
        if self._stations_df is None:
            await self.load_stations()

        return self._stations_df[self._stations_df["is_coastal"] == True].copy()

    async def get_station_count(self) -> int:
        """Get total number of stations."""
        if self._stations_df is None:
            await self.load_stations()

        return len(self._stations_df)


stations_service = StationsService()
