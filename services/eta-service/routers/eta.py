from __future__ import annotations

import datetime as dt_module
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from config import settings
from models.inference_router import predict as route_predict

router = APIRouter(prefix="/api/v1")

_SUPPORTED_MODELS = {"physics", "xgboost", "sarima"}


def _parse_snapshot(raw: bytes) -> dict[str, Any]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)


def _get_redis_client():
    try:
        import redis

        return redis.Redis(host="redis", port=6379)
    except Exception:

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


@router.get("/eta/{trip_id}/{stop_id}")
def get_eta(
    trip_id: str,
    stop_id: int,
    model: str = Query(default=None),
):
    """Return ETA for a given (tripId, stopId)."""
    selected_model = (model or settings.default_model).lower().strip()
    if selected_model not in _SUPPORTED_MODELS:
        raise HTTPException(status_code=400, detail=f"Unsupported model '{selected_model}'")

    redis_client = _get_redis_client()
    key = f"eta:trip:{trip_id}:snapshot"
    raw = redis_client.get(key)
    if not raw:
        raise HTTPException(status_code=503, detail=f"No real-time snapshot for trip {trip_id}")

    snapshot = _parse_snapshot(raw)
    stops = snapshot.get("stopsAhead") or []
    matched = None
    for stop in stops:
        try:
            if int(stop.get("stopId")) == int(stop_id):
                matched = stop
                break
        except Exception:
            continue

    if matched is None:
        raise HTTPException(status_code=404, detail=f"Stop {stop_id} not found")

    distance_m = float(
        matched.get("distanceAlongRouteMeters", snapshot.get("distanceToNextStop", 0.0))
    )
    speed_ms = float(snapshot.get("speed", 0.0))
    stops_remaining = int(snapshot.get("stopsRemaining", 1))
    segment_mode = str(snapshot.get("segmentMode", "urban"))

    outcome = route_predict(
        distance_m,
        speed_ms,
        stops_remaining=stops_remaining,
        dt=_parse_timestamp(snapshot.get("timestamp")),
        model_name=selected_model,
        segment_mode=segment_mode,
        route_id=snapshot.get("routeId"),
        stop_id=int(stop_id),
    )

    return {
        "tripId": trip_id,
        "busId": snapshot.get("busId"),
        "stopId": int(stop_id),
        "eta_seconds": float(outcome.result.eta_seconds),
        "distance_m": distance_m,
        "speed_ms": speed_ms,
        "model_used": outcome.model_used,
        "model_version": outcome.model_version,
        "segment_mode": outcome.segment_mode,
        "clamped": bool(outcome.result.clamped),
        "fallback": outcome.fallback,
        "timestamp": snapshot.get("timestamp"),
    }
