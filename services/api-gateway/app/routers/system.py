import socket
from datetime import datetime, timezone
from typing import Dict
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from app.config import settings

router = APIRouter(tags=["System"])

SERVICE_START_TIME = datetime.now(timezone.utc)

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
    influx_ok = _can_get_http(f"http://{settings.influxdb_host}:{settings.influxdb_port}/ping")

    return {
        "postgres": "up" if _can_open_tcp(settings.postgres_host, settings.postgres_port) else "down",
        "redis": "up" if _can_open_tcp(settings.redis_host, settings.redis_port) else "down",
        "kafka": "up" if _can_open_tcp(settings.kafka_host, settings.kafka_port) else "down",
        "influxdb": "up" if influx_ok else "down",
    }

@router.get("/health")
def health() -> Dict[str, object]:
    return {
        "status": "healthy",
        "service": "api-gateway",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": _dependency_status(),
    }

@router.get("/metrics", response_class=PlainTextResponse)
def metrics(request: Request) -> str:
    uptime_seconds = int((datetime.now(timezone.utc) - SERVICE_START_TIME).total_seconds())
    # Safely get request count from app state
    request_count = getattr(request.app.state, "request_count", 0)

    return "\n".join(
        [
            "# HELP api_gateway_requests_total Total HTTP requests handled by API gateway",
            "# TYPE api_gateway_requests_total counter",
            f"api_gateway_requests_total {request_count}",
            "# HELP api_gateway_uptime_seconds Service uptime in seconds",
            "# TYPE api_gateway_uptime_seconds gauge",
            f"api_gateway_uptime_seconds {uptime_seconds}",
            "",
        ]
    )

@router.get("/api/v1/status")
def api_v1_status() -> Dict[str, str]:
    return {"status": "ok", "service": "api-gateway", "version": "v1"}
