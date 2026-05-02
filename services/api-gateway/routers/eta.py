# services/api-gateway/routers/eta.py
# ETA endpoint — reads bus position from Redis, computes AI or physics ETA,
# writes to InfluxDB, and returns the prediction (Issue #23).

from typing import Any, Dict, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from services.eta_service import compute_bus_eta, write_eta_to_influx
from services.route_service import get_stop, get_bus

router = APIRouter(prefix="/api/v1/eta", tags=["eta"])


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
