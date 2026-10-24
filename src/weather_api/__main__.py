import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "weather_api.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        timeout_keep_alive=75,
    )


if __name__ == "__main__":
    main()
