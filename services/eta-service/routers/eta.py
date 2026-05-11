from __future__ import annotations

import datetime as dt_module
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from models.eta import compute_eta

router = APIRouter(prefix="/api/v1")


def _parse_snapshot(raw: bytes) -> dict[str, Any]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)


def _get_redis_client():
    try:
        import redis

        from app.config import settings

        return redis.Redis(host=settings.redis_host, port=settings.redis_port)
    except ImportError:
        class _FakeRedis:
            def get(self, *args, **kwargs):
                return None

        return _FakeRedis()


def _parse_timestamp(timestamp: Any) -> dt_module.datetime | None:
    if not timestamp:
        return None
    try:
        return dt_module.datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except Exception:
        return None


def _predict_eta_from_snapshot(snapshot: dict[str, Any], stop: dict[str, Any], model: str) -> tuple[float, str, bool]:
    distance_m = float(stop.get("distanceAlongRouteMeters", snapshot.get("distanceToNextStop", 0.0)))
    speed_ms = float(snapshot.get("speed", 0.0))
    stops_remaining = int(snapshot.get("stopsRemaining", 1))
    timestamp = _parse_timestamp(snapshot.get("timestamp"))

    if model == "sarima":
        try:
            from models.sarima_eta import forecast_eta_sarima

            route_id = str(snapshot.get("routeId", ""))
            sarima_result = forecast_eta_sarima(route_id, int(stop.get("stopId")), timestamp)
            if sarima_result is not None:
                return sarima_result, "sarima", False
        except Exception:
            pass
        # Fall through to xgboost when no SARIMA artifact is available

    if model in {"xgboost", "sarima"}:
        try:
            from models.ml_eta_xgb import predict_eta_xgb

            result = predict_eta_xgb(
                distance_m,
                speed_ms,
                stops_remaining=stops_remaining,
                dt=timestamp,
            )
            return result.eta_seconds, "xgboost", result.clamped
        except Exception:
            pass

    physics = compute_eta(distance_m, speed_ms)
    return physics.eta_seconds, "physics", physics.clamped


@router.get("/eta/{trip_id}/{stop_id}")
def get_eta(trip_id: str, stop_id: int, model: str = Query("physics")):
    """Return ETA for a given (tripId, stopId).

    Example request:
        GET /api/v1/eta/TRIP-2026-001/42?model=xgboost

    Example response:
        {
          "tripId": "TRIP-2026-001",
          "busId": "BUS-001",
          "stopId": 42,
          "eta_seconds": 120.5,
          "distance_m": 234.5,
          "speed_ms": 1.95,
          "model_used": "xgboost",
          "clamped": false,
          "timestamp": "2026-05-05T01:00:00Z"
        }
    """
    if model not in {"physics", "xgboost", "sarima"}:
        raise HTTPException(status_code=400, detail=f"Unsupported model '{model}'")

    redis_client = _get_redis_client()

    key = f"eta:trip:{trip_id}:snapshot"
    raw = redis_client.get(key)
    if not raw:
        raise HTTPException(status_code=503, detail=f"No real-time snapshot for trip {trip_id}")

    snapshot = _parse_snapshot(raw)

    # Find stop in stopsAhead
    stops = snapshot.get("stopsAhead") or []
    matched = None
    for s in stops:
        try:
            if int(s.get("stopId")) == int(stop_id):
                matched = s
                break
        except Exception:
            continue

    if matched is None:
        raise HTTPException(status_code=404, detail=f"Stop {stop_id} not found")

    eta_seconds, model_used, clamped = _predict_eta_from_snapshot(snapshot, matched, model)

    response = {
        "tripId": trip_id,
        "busId": snapshot.get("busId"),
        "stopId": int(stop_id),
        "eta_seconds": float(eta_seconds),
        "distance_m": float(matched.get("distanceAlongRouteMeters", snapshot.get("distanceToNextStop", 0.0))),
        "speed_ms": float(snapshot.get("speed", 0.0)),
        "model_used": model_used,
        "clamped": bool(clamped),
        "timestamp": snapshot.get("timestamp"),
    }

    return response
