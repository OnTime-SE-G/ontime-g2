# services/api-gateway/main.py
# OnTime API Gateway — FastAPI application.
# Serves health, metrics, and API endpoints for the frontend.

import os
import socket
from datetime import datetime, timezone
from typing import Dict
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from routers import buses, eta, live, routes as routes_router

app = FastAPI(
    title="OnTime API Gateway",
    version="0.1.0",
    description="G2 API gateway service for REST and WebSocket endpoints.",
)

SERVICE_START_TIME = datetime.now(timezone.utc)
app.state.request_count = 0

app.include_router(routes_router.router)
app.include_router(buses.router)
app.include_router(eta.router)
app.include_router(live.router)


def _can_open_tcp(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _can_get_http(url: str, timeout: float = 0.6) -> bool:
    try:
        with urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 500
    except (URLError, OSError):
        return False


def _dependency_status() -> Dict[str, str]:
    postgres_host = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    kafka_host = os.getenv("KAFKA_HOST", "localhost")
    kafka_port = int(os.getenv("KAFKA_PORT", "9092"))
    influx_host = os.getenv("INFLUXDB_HOST", "localhost")
    influx_port = int(os.getenv("INFLUXDB_PORT", "8086"))

    influx_ok = _can_get_http(f"http://{influx_host}:{influx_port}/ping")

    return {
        "postgres": "up" if _can_open_tcp(postgres_host, postgres_port) else "down",
        "redis": "up" if _can_open_tcp(redis_host, redis_port) else "down",
        "kafka": "up" if _can_open_tcp(kafka_host, kafka_port) else "down",
        "influxdb": "up" if influx_ok else "down",
    }


@app.middleware("http")
async def count_requests(request, call_next):
    response = await call_next(request)
    app.state.request_count += 1
    return response


@app.get("/health")
def health() -> Dict[str, object]:
    return {
        "status": "healthy",
        "service": "api-gateway",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": _dependency_status(),
    }


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    uptime_seconds = int((datetime.now(timezone.utc) -
                         SERVICE_START_TIME).total_seconds())

    return "\n".join(
        [
            "# HELP api_gateway_requests_total Total HTTP requests handled by API gateway",
            "# TYPE api_gateway_requests_total counter",
            f"api_gateway_requests_total {app.state.request_count}",
            "# HELP api_gateway_uptime_seconds Service uptime in seconds",
            "# TYPE api_gateway_uptime_seconds gauge",
            f"api_gateway_uptime_seconds {uptime_seconds}",
            "",
        ]
    )


@app.get("/api/v1/status")
def api_v1_status() -> Dict[str, str]:
    return {"status": "ok", "service": "api-gateway", "version": "v1"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
