"""HTTP proxy to route-service for route and stop data."""
import os
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter, HTTPException

ROUTE_SERVICE_URL = os.getenv("ROUTE_SERVICE_URL", "http://localhost:8002")

router = APIRouter(prefix="/api/v1/routes", tags=["routes"])


@router.get("", response_model=List[Dict[str, Any]])
async def get_routes():
    """List all routes (proxied to route-service)."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{ROUTE_SERVICE_URL}/routes/", timeout=10.0)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="route-service unavailable")
    return resp.json()


@router.get("/{route_id}", response_model=Dict[str, Any])
async def get_route_by_id(route_id: int):
    """Get a single route with stops (proxied to route-service)."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{ROUTE_SERVICE_URL}/routes/{route_id}", timeout=10.0)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="route-service unavailable")
    return resp.json()
