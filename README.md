# MTA Rainfall API

This is a FastAPI application that provides precipitation, tide, and flood‑risk reporting for NYC MTA subway stations. It supports current conditions and some historical reports with Excel/CSV exports.

## Features & and Their Source

- Current precipitation data from NOAA MRMS (precip rate, 1‑hour, 6‑hour)
- Historical precipitation from NCEP Stage IV hourly archive
- Tide levels from NOAA Tides & Currents API (current and historical at time)
- Daily precipitation totals from NOAA NCEI CDO (Central Park, JFK, LGA) with fallback to last 7 days if same‑day is unavailable
- 6/24 hour precipitation forecasts from NWS gridpoint API (today only)
- Risk calculation based on station structure type, precipitation rate/accumulation, and tide level
- Excel/CSV export compatible with Power BI

## Data Sources

| Source | Data | Update Frequency |
|--------|------|------------------|
| NOAA MRMS | Current precip rate, 1hr/6hr accumulation | ~2 minutes |
| NCEP Stage IV (IEM archive) | Historical hourly precipitation (2021‑present) | Hourly |
| NOAA Tides | Water levels at The Battery and Kings Point | 6 minutes |
| NOAA NCEI CDO (GHCN-Daily) | Central Park / JFK / LGA daily precip totals | Daily |
| NWS Gridpoint API | 6hr/24hr precipitation forecasts (today only) | Hourly |
| MTA | Station locations, structure types | Static (cached) |

## Installation

### Prerequisites

- Python 3.10+
- pip or conda


### Setup

1. Clone the repository:
```bash
cd mta-flood-api
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy .env.example → .env and set:
NCEI_CDO_TOKEN=...
```bash
cp .env.example .env
```

5. Run the application:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

6. Access the API documentation at http://localhost:8000/docs

## API Endpoints

### GET /api/report

Generate a full precipitation report for all MTA stations.

**Query Parameters:**
- `date` (optional): Report date (YYYY-MM-DD), defaults to today
- `time` (optional): Report time (HH:MM, 24‑hour)
- `borough` (optional): Filter by Manhattan, Brooklyn, Queens, Bronx, or Staten Island
- `stations` (optional): Comma‑separated station names to include
- `risk_only` (optional): Only return FLOOD WATCH or FLOOD WARNING stations
- `format` (optional): Output format - json, csv, or xlsx

**Example:**
```bash
# Get JSON report
curl "http://localhost:8000/api/report"

# Get Excel report for Manhattan only
curl "http://localhost:8000/api/report?borough=Manhattan&format=xlsx" -o report.xlsx

# Get Excel report for a specific date/time - I chose January 10th  2025
curl "http://localhost:8000/api/report?date=2025-01-10&time=22:00&format=xlsx" -o ida.xlsx

# Get only high-risk stations
curl "http://localhost:8000/api/report?risk_only=true"
```

### GET /api/current

Quick snapshot of current high-risk stations.

**Example:**
```bash
curl "http://localhost:8000/api/current"
```

**Response:**
```json
{
  "timestamp": "2026-01-23T14:30:00Z",
  "high_risk_stations": ["145 St", "Broad Channel"],
  "at_risk_stations": ["Times Sq-42 St"],
  "high_risk_count": 2,
  "at_risk_count": 1
}
```

### GET /api/station/{station_name}

Get detailed info for a single station.

**Example:**
```bash
curl "http://localhost:8000/api/station/Times%20Sq-42%20St"
```

### GET /api/tides

Get current tide levels from NOAA stations.

**Example:**
```bash
curl "http://localhost:8000/api/tides"
```
### Likely issues & fixes

1. Python deps / pygrib
      - pygrib can be tricky on some systems (especially Windows).
      - On macOS/Linux, it usually installs via pip; on Windows you might need conda (conda install -c conda-forge pygrib).
2. numpy/pandas version compatibility
      - You might have to downgrade to numpy<2 because of binary incompatibilities.
      - On fresh environments, this may not be an issue, but if you see errors, pin numpy<2 in requirements.txt
3. Network access
      - MRMS, Stage IV archive, NWS, NOAA tides, and NCEI all require outbound HTTPS.
      - If you are on a corporate network, firewall/proxy could block. Health endpoint will show “degraded”.

### GET /api/health

Check availability of all data sources.

## Risk Calculation

Risk levels are calculated based on:

| Structure Type | HIGH Risk | AT RISK |
|----------------|-----------|---------|
| Subway (Underground) | Precip > 0.5 in/hr OR 6hr > 2.0 in | Precip > 0.25 in/hr OR 6hr > 1.0 in |
| Open Cut | Precip > 0.75 in/hr OR 6hr > 2.5 in | Precip > 0.4 in/hr OR 6hr > 1.5 in |
| Elevated | N/A | Precip > 1.5 in/hr |
| Coastal (with high tide) | Precip > 0.3 in/hr (tide > 5ft) | Precip > 0.15 in/hr (tide > 5ft) |

## Coastal Stations

These stations have tide data applied to their risk calculations:

- Broad Channel
- Howard Beach-JFK Airport
- Rockaway Park-Beach 116 St
- Beach 67 St, 60 St, 44 St, 36 St, 25 St
- Far Rockaway-Mott Av
- South Ferry
- Whitehall St-South Ferry
- Coney Island-Stillwell Av

## Excel Report Format

The Excel export includes:

| Column | Description |
|--------|-------------|
| Date | Report date |
| Time | Report generation time |
| Time Zone | Time zone for report time (America/New_York) |
| Station Line | MTA line name |
| Stop Name | MTA stop name |
| Borough | NYC borough |
| CBD | Central Business District indicator (from MTA data) |
| Daytime Routes | MTA daytime routes |
| Structure | Station structure type |
| GTFS Latitude | Station latitude |
| GTFS Longitude | Station longitude |
| Precip Rate (in/hr) | Current precipitation rate |
| 1hr Accumulation (in) | 1-hour precipitation total |
| 6hr Accumulation (in) | 6-hour precipitation total |
| Tide Level (ft) | Current tide level (coastal only) |
| Central Park Daily (in) | Daily total precip at Central Park (GHCN-Daily) |
| Central Park Daily Date | Date of the daily total used (fallback within last 7 days) |
| JFK Daily (in) | Daily total precip at JFK Airport (GHCN-Daily) |
| JFK Daily Date | Date of the daily total used (fallback within last 7 days) |
| LaGuardia Daily (in) | Daily total precip at LaGuardia Airport (GHCN-Daily) |
| LaGuardia Daily Date | Date of the daily total used (fallback within last 7 days) |
| Forecast 6hr (in) | Forecast total precipitation next 6 hours (NWS) |
| Forecast 24hr (in) | Forecast total precipitation next 24 hours (NWS) |
| Predicted Risk 6hr | Risk level based on 6-hour forecast |
| Predicted Risk 24hr | Risk level based on 24-hour forecast |
| Risk Level | FLOOD WARNING, FLOOD WATCH, or CLEAR |
| Risk Reason | Short explanation of why the risk level was assigned |
| Source | Data sources (NOAA MRMS / NOAA CDO / NWS) |

## Historical vs Current Behavior

- **Today:** MRMS + current tides + NWS forecasts
- **Past dates (2021‑present):** Stage IV hourly precipitation + tides at requested time, no forecasts

## Limitations

- Historical precipitation depends on archive availability; some hours may be missing.
- Daily station totals (CDO) are posted after the day ends; the API falls back to the most recent available day (up to 7 days).

## Configuration

All thresholds can be customized via environment variables. See `.env.example` for available options.

## Development

### Project Structure

```
mta-flood-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + endpoints
│   ├── config.py            # Settings and thresholds
│   ├── models.py            # Pydantic schemas
│   ├── services/
│   │   ├── mrms.py          # NOAA MRMS client
│   │   ├── tides.py         # NOAA Tides client
│   │   └── stations.py      # MTA station loader
│   ├── utils/
│   │   ├── risk.py          # Risk calculation
│   │   └── excel.py         # Excel generation
│   └── data/
│       └── stations.csv     # Cached station data
├── requirements.txt
├── .env.example
└── README.md
```

### Running Tests

```bash
pytest tests/
```

## License

MIT
