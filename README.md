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
| GET    | `/health/upstream`  | Diagnostic: is Open-Meteo reachable? (always 200) |
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
| `PORT`                 | `8000` (`8080` in Docker) | Bind port; platforms like Unkey set this for you |
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
docker run -p 8080:8080 weather-api
# or choose your own port:
docker run -e PORT=9000 -p 9000:9000 weather-api
```

The container binds to `0.0.0.0` and reads the `PORT` environment variable (default `8080`).

## Deploy on Unkey

[Unkey Deploy](https://www.unkey.com/docs) builds the `Dockerfile` in this repo and runs it
behind a gateway. The image already meets Unkey's runtime requirements:

- listens on the `PORT` env var that Unkey injects (default 8080)
- exits cleanly on `SIGTERM` (Python runs as PID 1 via exec-form `CMD`, uvicorn drains requests)
- writes nothing to local disk, well under the 128 MiB limit

**From GitHub (recommended):** connect this repo in the Unkey dashboard, and in
**App settings > Build** set the Dockerfile path to `Dockerfile` with root directory `.`.
Pushes to your default branch deploy to production; other branches get previews.

**Automatic build (no Dockerfile):** Unkey and Railway build with Railpack, which detects this
project as a FastAPI app from the root `main.py` and `requirements.txt`, then starts it with
`uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}`. If the build fails with
*"Railpack could not determine how to build the app"*, the build directory doesn't contain
these files. Either move the project files to the repo root (they must not sit inside a
`weather-api/` subfolder), or set the app's **Root directory** to that subfolder.

**Start command:** `railpack.json` pins it to
`uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}`, so the app never depends on
auto-detection. `python main.py` also starts the server as a fallback.

**If you see `err:frontline:upstream:bad_gateway` (502):** an instance is running and accepted
the connection, but the request then failed (connection reset, app crash, OOM kill, or a
rollout replacing the instance). Check the runtime logs first, then:

| Symptom | Cause / fix |
| --- | --- |
| Log shows `Killed` or the instance restarts | Out of memory: raise the app's memory in runtime settings |
| Log shows a traceback | Fix the error it names (open an issue with the first lines) |
| Log is silent when you send a request | The request never reaches the app: check the port setting matches `PORT` |
| `/health` works, `/weather/*` doesn't | Call `/health/upstream`. It always returns 200 and says whether Open-Meteo is reachable from the host |
| Fails only right after a deploy | Transient while the old instance is replaced: retry in a minute |

Uvicorn runs with `--timeout-keep-alive 75` so idle keep-alive connections that the gateway
reuses are not closed early (its 5s default can cause sporadic 502s).

**If you see `err:frontline:capacity:no_running_instances` (503):** Unkey has no running,
ready instance for the deployment. The container is crashing on start, never became ready, or
listens on a different port than the app's configured port. Work through these in order:

1. Open the deployment in the Unkey dashboard and read the **runtime logs**. The first
   traceback or `Error:` line is the cause.
2. Check **App settings > Runtime** and make sure the port matches the `PORT` the app is given
   (8080 by default). The app always binds to `$PORT`.
3. Prefer the Dockerfile build: set **App settings > Build > Dockerfile** to `Dockerfile`.
   It is deterministic, unlike automatic detection.
4. Reproduce locally. If this works, the image is fine and the problem is platform settings:

   ```bash
   docker build -t weather-api .
   docker run --rm -e PORT=8080 -p 8080:8080 weather-api
   curl localhost:8080/health      # {"status":"ok",...}
   ```

**From the CLI** (deploys a pre-built image, so build and push it to a registry first):

```bash
docker build -t ghcr.io/<you>/weather-api:v0.1.0 .
docker push ghcr.io/<you>/weather-api:v0.1.0

export UNKEY_ROOT_KEY=unkey_xxx
export UNKEY_PROJECT=<project>
export UNKEY_APP=<app>
unkey deploy ghcr.io/<you>/weather-api:v0.1.0 --env=production
```

**Protecting the API:** no code changes are needed. Unkey can enforce API-key auth and rate
limits in front of the app (attach a keyspace under the app's Sentinel settings), so requests
without a valid key never reach this service. Use `/health` as the health-check path.

Unkey Deploy is in public beta, so check the [Unkey docs](https://www.unkey.com/docs) if a
setting name differs from the above.

## Project layout


```
main.py       root entrypoint (`main:app`) for auto-detecting platforms
railpack.json pins the start command for Railpack builds
requirements.txt  runtime deps for platform builds
src/weather_api/
  main.py     FastAPI app, routes, error handlers
  client.py   Open-Meteo client with a small TTL cache
  models.py   Pydantic response models
  config.py   Environment-based settings
tests/        pytest suite
```

## License

MIT
