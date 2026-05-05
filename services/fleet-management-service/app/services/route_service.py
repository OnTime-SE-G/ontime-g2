import os

import httpx
from fastapi import HTTPException


ROUTE_SERVICE_URL = os.getenv("ROUTE_SERVICE_URL", "http://route-service:8002")
ROUTE_SERVICE_TIMEOUT_SECONDS = 3.0


def validate_route_exists(route_id: int) -> None:
    url = f"{ROUTE_SERVICE_URL.rstrip('/')}/api/v1/routes/{route_id}"

    try:
        response = httpx.get(url, timeout=ROUTE_SERVICE_TIMEOUT_SECONDS)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail="Route service unavailable",
        ) from exc

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Route not found")

    if response.status_code >= 400:
        raise HTTPException(
            status_code=503,
            detail="Route service unavailable",
        )
