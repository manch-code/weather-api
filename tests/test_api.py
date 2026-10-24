import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from weather_api.client import (
    FORECAST_URL,
    GEOCODE_URL,
    LocationNotFound,
    UpstreamError,
    WeatherClient,
)
from weather_api.main import app, get_weather_client
from weather_api.models import Location, Units

RALEIGH = Location(name="Raleigh", latitude=35.78, longitude=-78.64, country="United States")

GEOCODE_PAYLOAD = {
    "results": [
        {
            "name": "Raleigh",
            "latitude": 35.78,
            "longitude": -78.64,
            "country": "United States",
            "admin1": "North Carolina",
            "timezone": "America/New_York",
        }
    ]
}

CURRENT_PAYLOAD = {
    "current_units": {
        "temperature_2m": "°C",
        "wind_speed_10m": "km/h",
        "precipitation": "mm",
    },
    "current": {
        "time": "2026-10-23T12:00",
        "temperature_2m": 18.5,
        "relative_humidity_2m": 55,
        "apparent_temperature": 17.9,
        "precipitation": 0.0,
        "weather_code": 2,
        "wind_speed_10m": 10.2,
        "wind_direction_10m": 220,
    },
}

DAILY_PAYLOAD = {
    "daily_units": {
        "temperature_2m_max": "°C",
        "wind_speed_10m_max": "km/h",
        "precipitation_sum": "mm",
    },
    "daily": {
        "time": ["2026-10-23", "2026-10-24"],
        "weather_code": [2, 61],
        "temperature_2m_max": [21.0, 19.0],
        "temperature_2m_min": [10.0, 12.0],
        "precipitation_sum": [0.0, 4.2],
        "wind_speed_10m_max": [15.0, 22.5],
    },
}


def make_client(handler) -> WeatherClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return WeatherClient(http, cache_ttl=0)


# --- WeatherClient unit tests (Open-Meteo mocked at the transport layer) ---------------


def test_geocode_parses_first_result():
    client = make_client(lambda req: httpx.Response(200, json=GEOCODE_PAYLOAD))
    loc = asyncio.run(client.geocode("Raleigh"))
    assert loc.name == "Raleigh"
    assert loc.region == "North Carolina"


def test_geocode_not_found():
    client = make_client(lambda req: httpx.Response(200, json={}))
    with pytest.raises(LocationNotFound):
        asyncio.run(client.geocode("Nowhereville"))


def test_current_parses_and_describes():
    client = make_client(lambda req: httpx.Response(200, json=CURRENT_PAYLOAD))
    result = asyncio.run(client.current(RALEIGH, Units.metric))
    assert result.current.temperature == 18.5
    assert result.current.description == "Partly cloudy"
    assert result.units.wind_speed == "km/h"


def test_imperial_units_are_requested():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json=CURRENT_PAYLOAD)

    asyncio.run(make_client(handler).current(RALEIGH, Units.imperial))
    assert seen["temperature_unit"] == "fahrenheit"
    assert seen["wind_speed_unit"] == "mph"


def test_forecast_parses_days():
    client = make_client(lambda req: httpx.Response(200, json=DAILY_PAYLOAD))
    result = asyncio.run(client.forecast(RALEIGH, 2, Units.metric))
    assert [d.date for d in result.daily] == ["2026-10-23", "2026-10-24"]
    assert result.daily[1].description == "Slight rain"


def test_upstream_http_error_becomes_upstream_error():
    client = make_client(lambda req: httpx.Response(500))
    with pytest.raises(UpstreamError):
        asyncio.run(client.geocode("Raleigh"))


def test_cache_avoids_second_request():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        return httpx.Response(200, json=GEOCODE_PAYLOAD)

    client = WeatherClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)), cache_ttl=60)

    async def twice():
        await client.geocode("Raleigh")
        await client.geocode("Raleigh")

    asyncio.run(twice())
    assert len(calls) == 1


# --- HTTP endpoint tests (full app, Open-Meteo mocked) ---------------------------------


@pytest.fixture
def api():
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(GEOCODE_URL):
            name = request.url.params["name"]
            return httpx.Response(200, json=GEOCODE_PAYLOAD if name == "Raleigh" else {})
        if url.startswith(FORECAST_URL):
            params = request.url.params
            payload = CURRENT_PAYLOAD if "current" in params else DAILY_PAYLOAD
            return httpx.Response(200, json=payload)
        return httpx.Response(404)

    app.dependency_overrides[get_weather_client] = lambda: make_client(handler)
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


def test_health(api):
    assert api.get("/health").json()["status"] == "ok"


def test_current_by_city(api):
    r = api.get("/weather/current", params={"city": "Raleigh"})
    assert r.status_code == 200
    body = r.json()
    assert body["location"]["name"] == "Raleigh"
    assert body["current"]["temperature"] == 18.5


def test_current_by_coordinates(api):
    r = api.get("/weather/current", params={"lat": 35.78, "lon": -78.64})
    assert r.status_code == 200


def test_forecast(api):
    r = api.get("/weather/forecast", params={"city": "Raleigh", "days": 2})
    assert r.status_code == 200
    assert len(r.json()["daily"]) == 2


def test_unknown_city_is_404(api):
    assert api.get("/weather/current", params={"city": "Nowhereville"}).status_code == 404


def test_missing_location_is_422(api):
    assert api.get("/weather/current").status_code == 422


def test_days_out_of_range_is_422(api):
    assert api.get("/weather/forecast", params={"city": "Raleigh", "days": 99}).status_code == 422


def test_root_entrypoint_exposes_app():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "root_main", Path(__file__).resolve().parents[1] / "main.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.app is app
