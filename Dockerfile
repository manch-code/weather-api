FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . \
    && useradd --system --no-create-home app

USER app

# Platforms like Unkey Deploy inject PORT at runtime (default 8080) and it
# overrides this value. Bind to all interfaces so the platform proxy can reach us.
ENV HOST=0.0.0.0 \
    PORT=8080
EXPOSE 8080

# Exec form: python runs as PID 1 and receives SIGTERM directly, so uvicorn
# drains in-flight requests and exits cleanly on shutdown.
CMD ["python", "-m", "weather_api"]
