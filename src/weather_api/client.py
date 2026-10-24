"""Async client for the Open-Meteo geocoding and forecast APIs (no API key needed)."""

from __future__ import annotations

import time
from typing import Any

import httpx

from .models import (
    CurrentResponse,
    CurrentWeather,
    DailyForecast,
    ForecastResponse,
    Location,
    UnitLabels,
    Units,
)

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes used by Open-Meteo.
WMO_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

CURRENT_FIELDS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,"
    "precipitation,weather_code,wind_speed_10m,wind_direction_10m"
)
DAILY_FIELDS = (
    "weather_code,temperature_2m_max,temperature_2m_min,"
    "precipitation_sum,wind_speed_10m_max"
)


class LocationNotFound(Exception):
    """Raised when a place name cannot be geocoded."""


class UpstreamError(Exception):
    """Raised when Open-Meteo is unreachable or returns an error."""


def describe(code: int) -> str:
    return WMO_CODES.get(code, "Unknown")


class WeatherClient:
    def __init__(self, http: httpx.AsyncClient, cache_ttl: int = 300) -> None:
        self._http = http
        self._cache_ttl = cache_ttl
        self._cache: dict[tuple, tuple[float, Any]] = {}

    async def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        key = (url, tuple(sorted(params.items())))
        hit = self._cache.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        try:
            response = await self._http.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise UpstreamError(f"Open-Meteo request failed: {exc}") from exc
        if self._cache_ttl > 0:
            self._cache[key] = (time.monotonic() + self._cache_ttl, data)
        return data

    async def geocode(self, query: str) -> Location:
        data = await self._get(
            GEOCODE_URL,
            {"name": query, "count": 1, "language": "en", "format": "json"},
        )
        results = data.get("results")
        if not results:
            raise LocationNotFound(query)
        r = results[0]
        return Location(
            name=r["name"],
            latitude=r["latitude"],
            longitude=r["longitude"],
            country=r.get("country"),
            region=r.get("admin1"),
            timezone=r.get("timezone"),
        )

    @staticmethod
    def _base_params(location: Location, units: Units) -> dict[str, Any]:
        imperial = units is Units.imperial
        return {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "timezone": "auto",
            "temperature_unit": "fahrenheit" if imperial else "celsius",
            "wind_speed_unit": "mph" if imperial else "kmh",
            "precipitation_unit": "inch" if imperial else "mm",
        }

    async def current(self, location: Location, units: Units) -> CurrentResponse:
        params = {**self._base_params(location, units), "current": CURRENT_FIELDS}
        data = await self._get(FORECAST_URL, params)
        try:
            c, u = data["current"], data["current_units"]
            return CurrentResponse(
                location=location,
                units=UnitLabels(
                    temperature=u["temperature_2m"],
                    wind_speed=u["wind_speed_10m"],
                    precipitation=u["precipitation"],
                ),
                current=CurrentWeather(
                    time=c["time"],
                    temperature=c["temperature_2m"],
                    feels_like=c["apparent_temperature"],
                    humidity=c["relative_humidity_2m"],
                    precipitation=c["precipitation"],
                    wind_speed=c["wind_speed_10m"],
                    wind_direction=c["wind_direction_10m"],
                    weather_code=c["weather_code"],
                    description=describe(c["weather_code"]),
                ),
            )
        except (KeyError, TypeError) as exc:
            raise UpstreamError(f"Unexpected Open-Meteo response: {exc!r}") from exc

    async def forecast(self, location: Location, days: int, units: Units) -> ForecastResponse:
        params = {
            **self._base_params(location, units),
            "daily": DAILY_FIELDS,
            "forecast_days": days,
        }
        data = await self._get(FORECAST_URL, params)
        try:
            d, u = data["daily"], data["daily_units"]
            daily = [
                DailyForecast(
                    date=d["time"][i],
                    temp_max=d["temperature_2m_max"][i],
                    temp_min=d["temperature_2m_min"][i],
                    precipitation_sum=d["precipitation_sum"][i],
                    wind_speed_max=d["wind_speed_10m_max"][i],
                    weather_code=d["weather_code"][i],
                    description=describe(d["weather_code"][i]),
                )
                for i in range(len(d["time"]))
            ]
            return ForecastResponse(
                location=location,
                units=UnitLabels(
                    temperature=u["temperature_2m_max"],
                    wind_speed=u["wind_speed_10m_max"],
                    precipitation=u["precipitation_sum"],
                ),
                daily=daily,
            )
        except (KeyError, TypeError, IndexError) as exc:
            raise UpstreamError(f"Unexpected Open-Meteo response: {exc!r}") from exc
