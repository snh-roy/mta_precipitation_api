from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from app.config import COASTAL_STATIONS, VALID_BOROUGHS, get_settings
from app.models import (
    CurrentStatusResponse,
    FullReportResponse,
    ReportFormat,
    RiskLevel,
    StationDetailResponse,
    StationReport,
    TidesResponse,
)
from app.services.mrms import mrms_service
from app.services.stations import stations_service
from app.services.tides import tides_service
from app.services.cdo import cdo_service
from app.services.forecast import forecast_service
from app.utils.excel import generate_csv_report, generate_excel_report
from app.utils.risk import calculate_predicted_risk, calculate_risk, calculate_risk_with_reason

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Flood risk monitoring API for NYC MTA subway stations using NOAA MRMS precipitation data and tide levels.",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.on_event("startup")
async def startup_event():
    """Load station data on startup."""
    await stations_service.load_stations()


@app.get("/")
async def root():
    """API health check and info."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "operational",
        "docs_url": "/docs",
    }


@app.get("/api/report", response_model=FullReportResponse)
async def get_report(
    date: Optional[str] = Query(None, description="Report date (YYYY-MM-DD), defaults to today"),
    borough: Optional[str] = Query(None, description="Filter by borough"),
    risk_only: bool = Query(False, description="Only return HIGH or AT RISK stations"),
    format: ReportFormat = Query(ReportFormat.JSON, description="Output format: json, csv, or xlsx"),
):
    """
    Generate a full precipitation report for all MTA stations.

    Returns precipitation data, tide levels (for coastal stations), and
    calculated flood risk for each subway station.
    """
    # Validate borough if provided
    if borough and borough not in VALID_BOROUGHS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid borough. Must be one of: {', '.join(VALID_BOROUGHS)}",
        )

    # Get report date
    local_tz = ZoneInfo("America/New_York")
    generated_at = datetime.now(timezone.utc)
    generated_local = generated_at.astimezone(local_tz)
    report_date = date or generated_local.strftime("%Y-%m-%d")
    is_today = report_date == generated_local.strftime("%Y-%m-%d")

    try:
        # Get stations
        stations_df = await stations_service.get_stations(borough=borough)

        # Get precipitation data
        try:
            stations_df = await mrms_service.get_station_precipitation(stations_df)
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"NOAA MRMS data unavailable: {str(e)}",
            )

        # Get tide level for coastal stations
        tide_level = await tides_service.get_current_tide_level()

        # Fetch daily totals from NCEI CDO (Central Park, JFK, LaGuardia)
        cdo_totals = await cdo_service.get_daily_precip_totals(report_date)

        # Build station reports
        station_reports = []
        for _, row in stations_df.iterrows():
            is_coastal = row.get("is_coastal", False) or row["station_name"] in COASTAL_STATIONS
            station_tide = tide_level if is_coastal else None

            risk, risk_reason = calculate_risk_with_reason(
                structure=row["structure"],
                precip_rate_in_hr=row.get("precip_rate_in_hr", 0),
                accum_6hr_in=row.get("accum_6hr_in", 0),
                tide_level_ft=station_tide,
                is_coastal=is_coastal,
            )

            forecast_6hr_in = None
            forecast_24hr_in = None
            predicted_risk_6hr = None
            predicted_risk_24hr = None

            if is_today:
                forecast_6hr_in, forecast_24hr_in = await forecast_service.get_forecast_totals(
                    row["latitude"], row["longitude"]
                )

                if forecast_6hr_in is not None:
                    predicted_risk_6hr = calculate_predicted_risk(
                        structure=row["structure"],
                        forecast_total_in=forecast_6hr_in,
                        window_hours=6,
                        tide_level_ft=station_tide,
                        is_coastal=is_coastal,
                    )

                if forecast_24hr_in is not None:
                    predicted_risk_24hr = calculate_predicted_risk(
                        structure=row["structure"],
                        forecast_total_in=forecast_24hr_in,
                        window_hours=24,
                        tide_level_ft=station_tide,
                        is_coastal=is_coastal,
                    )

            # Filter if risk_only is requested
            if risk_only and risk == RiskLevel.LOW:
                continue

            # Map borough abbreviation to full name
            borough_map = {"M": "Manhattan", "Bk": "Brooklyn", "Q": "Queens", "Bx": "Bronx", "SI": "Staten Island"}
            full_borough = borough_map.get(row["borough"], row["borough"])

            report = StationReport(
                station_name=row["station_name"],
                borough=full_borough,
                structure=row["structure"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                precip_rate_in_hr=round(row.get("precip_rate_in_hr", 0), 4),
                accum_1hr_in=round(row.get("accum_1hr_in", 0), 4),
                accum_6hr_in=round(row.get("accum_6hr_in", 0), 4),
                tide_level_ft=round(station_tide, 2) if station_tide else None,
                central_park_daily_in=cdo_totals.get("central_park_daily_in"),
                jfk_daily_in=cdo_totals.get("jfk_daily_in"),
                lga_daily_in=cdo_totals.get("lga_daily_in"),
                forecast_6hr_in=round(forecast_6hr_in, 4)
                if forecast_6hr_in is not None
                else None,
                forecast_24hr_in=round(forecast_24hr_in, 4)
                if forecast_24hr_in is not None
                else None,
                predicted_risk_6hr=predicted_risk_6hr,
                predicted_risk_24hr=predicted_risk_24hr,
                risk_level=risk,
                risk_reason=risk_reason,
                source="NOAA MRMS; NOAA CDO; NWS",
            )
            station_reports.append(report)

        # Count risk levels
        high_count = sum(1 for s in station_reports if s.risk_level == RiskLevel.HIGH)
        at_risk_count = sum(1 for s in station_reports if s.risk_level == RiskLevel.AT_RISK)

        # Handle different output formats
        if format == ReportFormat.XLSX:
            excel_file = generate_excel_report(station_reports, report_date, generated_local)
            filename = f"mta_flood_report_{report_date}.xlsx"
            return StreamingResponse(
                excel_file,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )

        if format == ReportFormat.CSV:
            csv_content = generate_csv_report(station_reports, report_date, generated_local)
            filename = f"mta_flood_report_{report_date}.csv"
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )

        # Default: JSON response
        return FullReportResponse(
            generated_at=generated_local,
            report_date=report_date,
            source="NOAA MRMS; NOAA CDO; NWS",
            station_count=len(station_reports),
            high_risk_count=high_count,
            at_risk_count=at_risk_count,
            stations=station_reports,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")


@app.get("/api/current", response_model=CurrentStatusResponse)
async def get_current_status():
    """
    Get a quick snapshot of current high-risk stations.

    Returns lists of station names currently at HIGH or AT RISK levels.
    """
    try:
        stations_df = await stations_service.get_stations()

        try:
            stations_df = await mrms_service.get_station_precipitation(stations_df)
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"NOAA MRMS data unavailable: {str(e)}",
            )

        tide_level = await tides_service.get_current_tide_level()

        high_risk = []
        at_risk = []

        for _, row in stations_df.iterrows():
            is_coastal = row.get("is_coastal", False) or row["station_name"] in COASTAL_STATIONS
            station_tide = tide_level if is_coastal else None

            risk = calculate_risk(
                structure=row["structure"],
                precip_rate_in_hr=row.get("precip_rate_in_hr", 0),
                accum_6hr_in=row.get("accum_6hr_in", 0),
                tide_level_ft=station_tide,
                is_coastal=is_coastal,
            )

            if risk == RiskLevel.HIGH:
                high_risk.append(row["station_name"])
            elif risk == RiskLevel.AT_RISK:
                at_risk.append(row["station_name"])

        return CurrentStatusResponse(
            timestamp=datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York")),
            high_risk_stations=high_risk,
            at_risk_stations=at_risk,
            high_risk_count=len(high_risk),
            at_risk_count=len(at_risk),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


@app.get("/api/station/{station_name}", response_model=StationDetailResponse)
async def get_station_detail(station_name: str):
    """
    Get detailed information for a single station.

    Includes current precipitation data, tide level (if coastal),
    and calculated risk level.
    """
    station = await stations_service.get_station_by_name(station_name)

    if not station:
        raise HTTPException(
            status_code=404,
            detail=f"Station '{station_name}' not found",
        )

    try:
        precip_data = await mrms_service.get_single_station_precipitation(
            station["latitude"],
            station["longitude"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"NOAA MRMS data unavailable: {str(e)}",
        )

    is_coastal = station.get("is_coastal", False) or station["station_name"] in COASTAL_STATIONS
    tide_level = None

    if is_coastal:
        tide_level = await tides_service.get_current_tide_level()

    risk, risk_reason = calculate_risk_with_reason(
        structure=station["structure"],
        precip_rate_in_hr=precip_data.get("precip_rate_in_hr", 0),
        accum_6hr_in=precip_data.get("accum_6hr_in", 0),
        tide_level_ft=tide_level,
        is_coastal=is_coastal,
    )

    report_date = datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    cdo_totals = await cdo_service.get_daily_precip_totals(report_date)

    forecast_6hr_in, forecast_24hr_in = await forecast_service.get_forecast_totals(
        station["latitude"], station["longitude"]
    )

    predicted_risk_6hr = None
    predicted_risk_24hr = None
    if forecast_6hr_in is not None:
        predicted_risk_6hr = calculate_predicted_risk(
            structure=station["structure"],
            forecast_total_in=forecast_6hr_in,
            window_hours=6,
            tide_level_ft=tide_level,
            is_coastal=is_coastal,
        )
    if forecast_24hr_in is not None:
        predicted_risk_24hr = calculate_predicted_risk(
            structure=station["structure"],
            forecast_total_in=forecast_24hr_in,
            window_hours=24,
            tide_level_ft=tide_level,
            is_coastal=is_coastal,
        )

    borough_map = {"M": "Manhattan", "Bk": "Brooklyn", "Q": "Queens", "Bx": "Bronx", "SI": "Staten Island"}

    return StationDetailResponse(
        station_id=str(station["station_id"]),
        station_name=station["station_name"],
        borough=borough_map.get(station["borough"], station["borough"]),
        structure=station["structure"],
        latitude=station["latitude"],
        longitude=station["longitude"],
        lines=station.get("daytime_routes"),
        precip_rate_in_hr=round(precip_data.get("precip_rate_in_hr", 0), 4),
        accum_1hr_in=round(precip_data.get("accum_1hr_in", 0), 4),
        accum_6hr_in=round(precip_data.get("accum_6hr_in", 0), 4),
        tide_level_ft=round(tide_level, 2) if tide_level else None,
        central_park_daily_in=cdo_totals.get("central_park_daily_in"),
        jfk_daily_in=cdo_totals.get("jfk_daily_in"),
        lga_daily_in=cdo_totals.get("lga_daily_in"),
        forecast_6hr_in=round(forecast_6hr_in, 4) if forecast_6hr_in is not None else None,
        forecast_24hr_in=round(forecast_24hr_in, 4) if forecast_24hr_in is not None else None,
        predicted_risk_6hr=predicted_risk_6hr,
        predicted_risk_24hr=predicted_risk_24hr,
        risk_level=risk,
        risk_reason=risk_reason,
        is_coastal=is_coastal,
        source="NOAA MRMS; NOAA CDO; NWS",
        last_updated=datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York")),
    )


@app.get("/api/tides", response_model=TidesResponse)
async def get_tides():
    """
    Get current tide levels from NOAA stations.

    Returns water level readings from The Battery and Kings Point stations.
    """
    try:
        readings = await tides_service.get_all_tide_readings()

        if not readings:
            raise HTTPException(
                status_code=503,
                detail="Tide data unavailable from NOAA",
            )

        return TidesResponse(
            timestamp=datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York")),
            readings=readings,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tides: {str(e)}")


@app.get("/api/health")
async def health_check():
    """
    Check availability of all data sources.
    """
    mrms_available = await mrms_service.is_available()
    tides_available = await tides_service.is_available()
    cdo_available = await cdo_service.is_available()
    station_count = await stations_service.get_station_count()

    return {
        "status": "healthy" if mrms_available and tides_available and cdo_available else "degraded",
        "data_sources": {
            "mrms": "available" if mrms_available else "unavailable",
            "tides": "available" if tides_available else "unavailable",
            "cdo": "available" if cdo_available else "unavailable",
            "stations": f"{station_count} loaded" if station_count > 0 else "not loaded",
        },
        "timestamp": datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York")).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
