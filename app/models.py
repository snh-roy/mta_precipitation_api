from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    HIGH = "FLOOD WARNING"
    AT_RISK = "FLOOD WATCH"
    LOW = "CLEAR"


class ReportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    XLSX = "xlsx"


class StationBase(BaseModel):
    station_id: str
    station_name: str
    borough: str
    structure: str
    latitude: float
    longitude: float


class StationPrecipitation(BaseModel):
    precip_rate_in_hr: Optional[float] = None
    accum_1hr_in: Optional[float] = None
    accum_6hr_in: Optional[float] = None


class StationTide(BaseModel):
    tide_level_ft: Optional[float] = None


class StationReport(BaseModel):
    line: Optional[str] = None
    station_name: str
    borough: str
    cbd: Optional[str] = None
    daytime_routes: Optional[str] = None
    structure: str
    latitude: float
    longitude: float
    precip_rate_in_hr: Optional[float] = None
    accum_1hr_in: Optional[float] = None
    accum_6hr_in: Optional[float] = None
    tide_level_ft: Optional[float] = None
    central_park_daily_in: Optional[float] = None
    central_park_daily_date: Optional[str] = None
    jfk_daily_in: Optional[float] = None
    jfk_daily_date: Optional[str] = None
    lga_daily_in: Optional[float] = None
    lga_daily_date: Optional[str] = None
    forecast_6hr_in: Optional[float] = None
    forecast_24hr_in: Optional[float] = None
    predicted_risk_6hr: Optional[RiskLevel] = None
    predicted_risk_24hr: Optional[RiskLevel] = None
    risk_level: RiskLevel
    risk_reason: Optional[str] = None
    source: str = "NOAA MRMS"


class FullReportResponse(BaseModel):
    generated_at: datetime
    report_date: str
    source: str = "NOAA MRMS"
    station_count: int
    high_risk_count: int
    at_risk_count: int
    stations: list[StationReport]


class CurrentStatusResponse(BaseModel):
    timestamp: datetime
    high_risk_stations: list[str]
    at_risk_stations: list[str]
    high_risk_count: int
    at_risk_count: int


class TideReading(BaseModel):
    station_id: str
    station_name: str
    water_level_ft: float
    timestamp: datetime
    datum: str = "MLLW"


class TidesResponse(BaseModel):
    timestamp: datetime
    readings: list[TideReading]


class StationDetailResponse(BaseModel):
    station_id: str
    station_name: str
    borough: str
    structure: str
    latitude: float
    longitude: float
    lines: Optional[str] = None
    precip_rate_in_hr: Optional[float] = None
    accum_1hr_in: Optional[float] = None
    accum_6hr_in: Optional[float] = None
    tide_level_ft: Optional[float] = None
    central_park_daily_in: Optional[float] = None
    central_park_daily_date: Optional[str] = None
    jfk_daily_in: Optional[float] = None
    jfk_daily_date: Optional[str] = None
    lga_daily_in: Optional[float] = None
    lga_daily_date: Optional[str] = None
    forecast_6hr_in: Optional[float] = None
    forecast_24hr_in: Optional[float] = None
    predicted_risk_6hr: Optional[RiskLevel] = None
    predicted_risk_24hr: Optional[RiskLevel] = None
    risk_level: RiskLevel
    risk_reason: Optional[str] = None
    is_coastal: bool
    source: str = "NOAA MRMS"
    last_updated: datetime


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
