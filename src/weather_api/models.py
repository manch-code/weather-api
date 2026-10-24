from enum import Enum

from pydantic import BaseModel


class Units(str, Enum):
    metric = "metric"
    imperial = "imperial"


class Location(BaseModel):
    name: str
    latitude: float
    longitude: float
    country: str | None = None
    region: str | None = None
    timezone: str | None = None


class UnitLabels(BaseModel):
    temperature: str
    wind_speed: str
    precipitation: str


class CurrentWeather(BaseModel):
    time: str
    temperature: float
    feels_like: float
    humidity: int
    precipitation: float
    wind_speed: float
    wind_direction: int
    weather_code: int
    description: str


class DailyForecast(BaseModel):
    date: str
    temp_max: float
    temp_min: float
    precipitation_sum: float
    wind_speed_max: float
    weather_code: int
    description: str


class CurrentResponse(BaseModel):
    location: Location
    units: UnitLabels
    current: CurrentWeather


class ForecastResponse(BaseModel):
    location: Location
    units: UnitLabels
    daily: list[DailyForecast]
