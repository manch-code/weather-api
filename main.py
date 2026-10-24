"""Root-level entrypoint for platforms that auto-detect `main:app` (Railpack, Railway, Unkey).

The real application lives in src/weather_api/. This shim puts `src/` on the import path so
the app runs without the package being pip-installed. Either of these works:

    uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --timeout-keep-alive 75
    python main.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from weather_api.main import app  # noqa: E402

__all__ = ["app"]

if __name__ == "__main__":
    # Fallback if a platform runs `python main.py` instead of the uvicorn command.
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",  # noqa: S104
        port=int(os.getenv("PORT", "8080")),
        timeout_keep_alive=75,
    )
