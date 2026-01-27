# MTA Flood Risk Monitoring API

A FastAPI application that provides real-time flood risk monitoring for NYC MTA subway stations by combining NOAA MRMS precipitation data with tide levels.

## Features

- Real-time precipitation data from NOAA MRMS (AWS S3)
- Tide levels from NOAA Tides & Currents API
- Daily precipitation totals from NOAA NCEI CDO (Central Park, JFK, LGA)
- 6/24 hour precipitation forecasts from NWS gridpoint API
- Risk calculation based on station structure type, precipitation rate, accumulation, and tide levels
- Predictive risk based on 6/24 hour forecast totals
- Excel/CSV export compatible with Power BI
- Full API documentation via Swagger UI

## Data Sources

| Source | Data | Update Frequency |
|--------|------|------------------|
| NOAA MRMS | Precipitation rate, 1hr/6hr accumulation | 2 minutes |
| NOAA Tides | Water levels at The Battery and Kings Point | 6 minutes |
| NOAA NCEI CDO (GHCN-Daily) | Central Park / JFK / LGA daily precip totals | Daily |
| NWS Gridpoint API | 6hr/24hr precipitation forecasts | Hourly |
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

4. Copy the environment file:
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
- `borough` (optional): Filter by Manhattan, Brooklyn, Queens, Bronx, or Staten Island
- `risk_only` (optional): Only return HIGH or AT RISK stations
- `format` (optional): Output format - json, csv, or xlsx

**Example:**
```bash
# Get JSON report
curl "http://localhost:8000/api/report"

# Get Excel report for Manhattan only
curl "http://localhost:8000/api/report?borough=Manhattan&format=xlsx" -o report.xlsx

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

The following stations have tide data applied to their risk calculations:

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
| Station Name | MTA station name |
| Borough | NYC borough |
| Structure | Station structure type |
| Precip Rate (in/hr) | Current precipitation rate |
| 1hr Accumulation (in) | 1-hour precipitation total |
| 6hr Accumulation (in) | 6-hour precipitation total |
| Tide Level (ft) | Current tide level (coastal only) |
| Central Park Daily (in) | Daily total precip at Central Park (GHCN-Daily) |
| JFK Daily (in) | Daily total precip at JFK Airport (GHCN-Daily) |
| LaGuardia Daily (in) | Daily total precip at LaGuardia Airport (GHCN-Daily) |
| Forecast 6hr (in) | Forecast total precipitation next 6 hours (NWS) |
| Forecast 24hr (in) | Forecast total precipitation next 24 hours (NWS) |
| Predicted Risk 6hr | Risk level based on 6-hour forecast |
| Predicted Risk 24hr | Risk level based on 24-hour forecast |
| Risk Level | HIGH, AT RISK, or LOW |
| Risk Reason | Short explanation of why the risk level was assigned |
| Source | Data sources (NOAA MRMS / NOAA CDO / NWS) |

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
