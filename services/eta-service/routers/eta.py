# services/eta-service/routers/eta.py
# ETA REST endpoint — accepts bus_id, stop coordinates, and returns ETA.
# The API gateway calls this service internally.

from typing import Any, Dict, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.eta_service import compute_bus_eta, write_eta_to_influx

router = APIRouter(prefix="/eta", tags=["eta"])


class EtaRequest(BaseModel):
    bus_id: str
    stop_id: int
    stop_lat: float
    stop_lon: float


@router.post("", response_model=Dict[str, Any])
def predict_eta(
    req: EtaRequest,
    model: Literal["ai", "physics"] = Query(default="ai"),
):
    """Compute ETA for a bus to reach a stop.

    Called by the API gateway after it resolves bus and stop data from
    PostgreSQL.  This service owns all ETA prediction logic.
    """
    use_ai = model == "ai"
    result = compute_bus_eta(req.bus_id, req.stop_lat, req.stop_lon, use_ai=use_ai)

    if result is None:
        raise HTTPException(
            status_code=503,
            detail=f"No real-time position available for bus {req.bus_id}",
        )

    write_eta_to_influx(req.bus_id, req.stop_id, result)

    return {
        "bus_id": req.bus_id,
        "stop_id": req.stop_id,
        "eta_seconds": round(result.eta_seconds, 1),
        "distance_m": round(result.distance_m, 1),
        "speed_ms": round(result.speed_ms, 2),
        "model_used": "physics" if (not use_ai or result.clamped) else "ai_gbr",
        "clamped": result.clamped,
    }
