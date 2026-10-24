from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from . import __version__
from .client import LocationNotFound, UpstreamError, WeatherClient
from .config import settings
from .models import CurrentResponse, ForecastResponse, Location, Units


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(
        timeout=settings.http_timeout,
        headers={"User-Agent": f"weather-api/{__version__}"},
    ) as http:
        app.state.weather = WeatherClient(http, cache_ttl=settings.cache_ttl)
        yield


app = FastAPI(
    title="Weather API",
    version=__version__,
    description="Current weather and forecasts, powered by Open-Meteo.",
    lifespan=lifespan,
)


@app.exception_handler(LocationNotFound)
async def location_not_found_handler(_: Request, exc: LocationNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": f"Location not found: {exc}"})


@app.exception_handler(UpstreamError)
async def upstream_error_handler(_: Request, exc: UpstreamError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


def get_weather_client(request: Request) -> WeatherClient:
    return request.app.state.weather


ClientDep = Annotated[WeatherClient, Depends(get_weather_client)]
CityQuery = Annotated[str | None, Query(min_length=1, max_length=100, description="City name")]
LatQuery = Annotated[float | None, Query(ge=-90, le=90)]
LonQuery = Annotated[float | None, Query(ge=-180, le=180)]


async def resolve_location(
    client: WeatherClient, city: str | None, lat: float | None, lon: float | None
) -> Location:
    if city:
        return await client.geocode(city)
    if lat is not None and lon is not None:
        return Location(name=f"{lat:.4f}, {lon:.4f}", latitude=lat, longitude=lon)
    raise HTTPException(status_code=422, detail="Provide either 'city' or both 'lat' and 'lon'.")


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {"name": app.title, "version": __version__, "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/health/upstream", tags=["meta"])
async def health_upstream(client: ClientDep) -> dict[str, str]:
    """Diagnostic: is Open-Meteo reachable from this host? Always returns HTTP 200."""
    try:
        await client.geocode("London")
    except LocationNotFound:
        pass  # Open-Meteo answered, so it is reachable
    except UpstreamError as exc:
        return {"open_meteo": "unreachable", "detail": str(exc)}
    return {"open_meteo": "reachable"}


@app.get("/weather/current", response_model=CurrentResponse, tags=["weather"])
async def current_weather(
    client: ClientDep,
    city: CityQuery = None,
    lat: LatQuery = None,
    lon: LonQuery = None,
    units: Units = Units.metric,
) -> CurrentResponse:
    location = await resolve_location(client, city, lat, lon)
    return await client.current(location, units)


@app.get("/weather/forecast", response_model=ForecastResponse, tags=["weather"])
async def weather_forecast(
    client: ClientDep,
    city: CityQuery = None,
    lat: LatQuery = None,
    lon: LonQuery = None,
    days: Annotated[int, Query(ge=1, le=16)] = 7,
    units: Units = Units.metric,
) -> ForecastResponse:
    location = await resolve_location(client, city, lat, lon)
    return await client.forecast(location, days, units)
