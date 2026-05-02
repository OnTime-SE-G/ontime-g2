# services/api-gateway/services/eta_service.py
# ETA service: reads bus position from Redis, computes physics-heuristic ETA,
# and writes the result to InfluxDB for analytics.

import math
import os
from datetime import datetime, timezone
from typing import Optional

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from cache import get_bus_position
from models.eta import EtaResult, compute_eta
from models.ml_eta import predict_eta as ml_predict_eta

# InfluxDB config from environment
_INFLUX_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
_INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN", "")
_INFLUX_ORG = os.getenv("INFLUXDB_ORG", "ontime")
_INFLUX_BUCKET = os.getenv("INFLUXDB_BUCKET", "eta_predictions")


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in metres between two WGS-84 coordinates."""
    R = 6_371_000.0  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def compute_bus_eta(
    bus_id: str,
    stop_lat: float,
    stop_lon: float,
    default_speed_ms: float = 5.0,
    use_ai: bool = True,
) -> Optional[EtaResult]:
    """Compute ETA from Redis-cached bus position to a stop.

    By default the AI (Gradient Boosting) model is tried first.  If the AI
    prediction falls outside a sanity band around the physics baseline it
    automatically falls back to the physics heuristic.  Pass use_ai=False to
    always use the pure physics model.

    Returns None when no cached position is available for the bus.
    """
    position = get_bus_position(bus_id)
    if position is None:
        return None

    distance_m = _haversine_m(
        position["lat"], position["lon"],
        stop_lat, stop_lon,
    )
    speed_ms = position.get("speed_ms", default_speed_ms)

    if use_ai:
        return ml_predict_eta(distance_m, speed_ms)
    return compute_eta(distance_m, speed_ms)


def write_eta_to_influx(bus_id: str, stop_id: int, result: EtaResult) -> None:
    """Persist an ETA prediction to InfluxDB (fire-and-forget, best-effort)."""
    if not _INFLUX_TOKEN:
        return  # skip silently when token is not configured

    try:
        with InfluxDBClient(url=_INFLUX_URL, token=_INFLUX_TOKEN, org=_INFLUX_ORG) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            point = (
                Point("eta_prediction")
                .tag("bus_id", bus_id)
                .tag("stop_id", str(stop_id))
                .field("eta_seconds", result.eta_seconds)
                .field("distance_m", result.distance_m)
                .field("speed_ms", result.speed_ms)
                .field("clamped", int(result.clamped))
                .time(datetime.now(timezone.utc), WritePrecision.SECONDS)
            )
            write_api.write(bucket=_INFLUX_BUCKET, record=point)
    except Exception:
        pass  # non-critical analytics path — never fail the HTTP request
