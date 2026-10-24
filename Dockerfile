FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . \
    && useradd --system --no-create-home app

USER app

# Unkey Deploy injects PORT (default 8080) and routes traffic to it.
ENV PORT=8080
EXPOSE 8080

# `exec` replaces the shell so uvicorn is PID 1 and receives SIGTERM directly,
# which lets it drain requests and exit cleanly. The host is hardcoded so a
# platform-provided HOST variable can never make the server bind to the wrong address.
# --timeout-keep-alive 75: uvicorn's 5s default closes idle connections that the gateway
# may still try to reuse, which shows up as sporadic 502s / connection resets.
CMD ["sh", "-c", "exec uvicorn weather_api.main:app --host 0.0.0.0 --port ${PORT:-8080} --timeout-keep-alive 75"]
