import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime settings, overridable with environment variables."""

    http_timeout: float = float(os.getenv("WEATHER_HTTP_TIMEOUT", "10"))
    cache_ttl: int = int(os.getenv("WEATHER_CACHE_TTL", "300"))  # seconds; 0 disables


settings = Settings()
