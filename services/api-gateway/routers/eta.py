"""Thin proxy for ETA — resolves bus/stop from route-service, delegates to eta-service."""
import os
from typing import Any, Dict, Literal

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/eta", tags=["eta"])

_ETA_SERVICE_URL = os.getenv("ETA_SERVICE_URL", "http://localhost:8001")
_ROUTE_SERVICE_URL = os.getenv("ROUTE_SERVICE_URL", "http://localhost:8002")


async def _get_stop(stop_id: int) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{_ROUTE_SERVICE_URL}/routes/", timeout=10.0)
            resp.raise_for_status()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="route-service unavailable")

    # Find the stop across all routes
    for route in resp.json():
        for stop in route.get("stops", []):
            if stop["id"] == stop_id:
                return stop
    raise HTTPException(status_code=404, detail=f"Stop {stop_id} not found")


@router.get("/{bus_id}/{stop_id}", response_model=Dict[str, Any])
async def get_eta(
    bus_id: int,
    stop_id: int,
    model: Literal["ai", "physics"] = Query(default="ai", description="ETA model to use"),
):
    """Return ETA (seconds) for a bus to reach a stop.

    - Resolves stop coordinates from route-service.
    - Delegates ETA computation to eta-service (AI GBR or physics).
    """
    stop = await _get_stop(stop_id)
    stop_lat = stop.get("lat")
    stop_lon = stop.get("lon")
    if stop_lat is None or stop_lon is None:
        raise HTTPException(status_code=422, detail=f"Stop {stop_id} has no location data")

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{_ETA_SERVICE_URL}/eta",
                params={"model": model},
                json={
                    "bus_id": str(bus_id),
                    "stop_id": stop_id,
                    "stop_lat": stop_lat,
                    "stop_lon": stop_lon,
                },
                timeout=5.0,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="eta-service unavailable")
