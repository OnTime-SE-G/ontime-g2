# services/api-gateway/routers/eta.py
# Thin proxy — resolves bus/stop data from PostgreSQL then delegates ETA
# computation to the dedicated eta-service microservice.

import os
from typing import Any, Dict, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from services.route_service import get_stop, get_bus

router = APIRouter(prefix="/api/v1/eta", tags=["eta"])

_ETA_SERVICE_URL = os.getenv("ETA_SERVICE_URL", "http://localhost:8001")


@router.get("/{bus_id}/{stop_id}", response_model=Dict[str, Any])
def get_eta(
    bus_id: int,
    stop_id: int,
    model: Literal["ai", "physics"] = Query(default="ai", description="ETA model to use"),
    db: Session = Depends(get_db),
):
    """Return ETA (seconds) for a bus to reach a stop.

    Resolves bus and stop data from PostgreSQL, then proxies the prediction
    request to the eta-service microservice which owns all ETA logic.
    """
    bus = get_bus(db, bus_id)
    if bus is None:
        raise HTTPException(status_code=404, detail=f"Bus {bus_id} not found")

    stop = get_stop(db, stop_id)
    if stop is None:
        raise HTTPException(status_code=404, detail=f"Stop {stop_id} not found")

    if stop.location is None:
        raise HTTPException(status_code=422, detail=f"Stop {stop_id} has no location data")

    from geoalchemy2.shape import to_shape
    point = to_shape(stop.location)
    stop_lon, stop_lat = point.x, point.y

    try:
        resp = httpx.post(
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
        raise HTTPException(status_code=503, detail="ETA service unavailable")



@router.get("/{bus_id}/{stop_id}", response_model=Dict[str, Any])
def get_eta(
    bus_id: int,
    stop_id: int,
    model: Literal["ai", "physics"] = Query(default="ai", description="ETA model to use"),
    db: Session = Depends(get_db),
):
    """Return ETA (seconds) for a bus to reach a stop.

    - Looks up stop coordinates from PostgreSQL via ORM.
    - Reads bus real-time position from Redis.
    - **AI model** (default): Gradient Boosting Regressor trained on distance,
      speed, hour-of-day, and day-of-week traffic patterns.  Falls back to
      physics if the prediction is outside a ±80% sanity band.
    - **Physics model** (`?model=physics`): pure distance ÷ speed heuristic.
    - Persists the prediction to InfluxDB (best-effort).
    """
    bus = get_bus(db, bus_id)
    if bus is None:
        raise HTTPException(status_code=404, detail=f"Bus {bus_id} not found")

    stop = get_stop(db, stop_id)
    if stop is None:
        raise HTTPException(status_code=404, detail=f"Stop {stop_id} not found")

    if stop.location is None:
        raise HTTPException(status_code=422, detail=f"Stop {stop_id} has no location data")

    from geoalchemy2.shape import to_shape
    point = to_shape(stop.location)
    stop_lon, stop_lat = point.x, point.y

    use_ai = model == "ai"
    result = compute_bus_eta(str(bus_id), stop_lat, stop_lon, use_ai=use_ai)
    if result is None:
        raise HTTPException(
            status_code=503,
            detail=f"No real-time position available for bus {bus_id}",
        )

    write_eta_to_influx(str(bus_id), stop_id, result)

    return {
        "bus_id": bus_id,
        "stop_id": stop_id,
        "eta_seconds": round(result.eta_seconds, 1),
        "distance_m": round(result.distance_m, 1),
        "speed_ms": round(result.speed_ms, 2),
        "model_used": "physics" if (not use_ai or result.clamped) else "ai_gbr",
        "clamped": result.clamped,
    }
