# Weather API

A small [FastAPI](https://fastapi.tiangolo.com/) service that returns current weather and
daily forecasts. Data comes from [Open-Meteo](https://open-meteo.com/), which needs **no API key**.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m weather_api
```

Then open <http://127.0.0.1:8000/docs> for interactive Swagger docs.

## Endpoints

| Method | Path                | Description                              |
| ------ | ------------------- | ---------------------------------------- |
| GET    | `/health`           | Liveness check                           |
| GET    | `/weather/current`  | Current conditions                       |
| GET    | `/weather/forecast` | Daily forecast (1–16 days, default 7)    |

### Query parameters

| Name    | Applies to    | Description                                              |
| ------- | ------------- | -------------------------------------------------------- |
| `city`  | both          | City name (geocoded via Open-Meteo)                      |
| `lat`, `lon` | both     | Coordinates; use instead of `city`                       |
| `days`  | forecast      | Number of days, 1–16 (default 7)                         |
| `units` | both          | `metric` (default: °C, km/h, mm) or `imperial` (°F, mph, in) |

Provide either `city` or both `lat` and `lon`.

### Example

```bash
curl "http://127.0.0.1:8000/weather/current?city=Raleigh&units=imperial"
```

```json
{
  "location": {
    "name": "Raleigh",
    "latitude": 35.78,
    "longitude": -78.64,
    "country": "United States",
    "region": "North Carolina",
    "timezone": "America/New_York"
  },
  "units": { "temperature": "°F", "wind_speed": "mp/h", "precipitation": "inch" },
  "current": {
    "time": "2026-10-23T12:00",
    "temperature": 65.3,
    "feels_like": 64.2,
    "humidity": 55,
    "precipitation": 0.0,
    "wind_speed": 6.3,
    "wind_direction": 220,
    "weather_code": 2,
    "description": "Partly cloudy"
  }
}
```

(Values are illustrative.)

### Errors

| Status | Meaning                                          |
| ------ | ------------------------------------------------ |
| 404    | City could not be found                          |
| 422    | Invalid or missing parameters                    |
| 502    | Open-Meteo unreachable or returned bad data      |

## Configuration

Set via environment variables (see `.env.example`):

| Variable               | Default     | Description                                  |
| ---------------------- | ----------- | -------------------------------------------- |
| `HOST`                 | `127.0.0.1` | Bind address for `python -m weather_api`     |
| `PORT`                 | `8000`      | Bind port                                    |
| `WEATHER_HTTP_TIMEOUT` | `10`        | Upstream request timeout (seconds)           |
| `WEATHER_CACHE_TTL`    | `300`       | In-memory cache TTL in seconds (0 disables)  |

## Development

```bash
pytest          # run tests (Open-Meteo is mocked; no network needed)
ruff check .    # lint
```

CI runs both on Python 3.10–3.13 via GitHub Actions.

## Docker

```bash
docker build -t weather-api .
docker run -p 8000:8000 weather-api
```

## Project layout

```
src/weather_api/
  main.py     FastAPI app, routes, error handlers
  client.py   Open-Meteo client with a small TTL cache
  models.py   Pydantic response models
  config.py   Environment-based settings
tests/        pytest suite
```

