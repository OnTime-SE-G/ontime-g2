import json
import logging
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from app.config import settings
from .training.feature_extraction import build_summary_vector

from models.isolation_forest_model import predict as if_predict

logger = logging.getLogger(__name__)

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000  # Radius of earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def distance_to_polyline(lat: float, lon: float, polyline: List[Tuple[float, float]]) -> float:
    """Calculate the shortest distance from a point to a polyline using segment projection."""
    if not polyline or len(polyline) < 1:
        return float('inf')
    if len(polyline) == 1:
        return haversine_distance(lat, lon, polyline[0][0], polyline[0][1])

    min_dist = float('inf')

    for i in range(len(polyline) - 1):
        p1 = polyline[i]
        p2 = polyline[i+1]

        seg_len = haversine_distance(p1[0], p1[1], p2[0], p2[1])
        if seg_len == 0:
            d = haversine_distance(lat, lon, p1[0], p1[1])
            min_dist = min(min_dist, d)
            continue

        d1 = haversine_distance(lat, lon, p1[0], p1[1])
        d2 = haversine_distance(lat, lon, p2[0], p2[1])

        # Projection ratio t using Law of Cosines simplified
        t = (d1**2 + seg_len**2 - d2**2) / (2 * seg_len**2)
        t = max(0.0, min(1.0, t))

        # Closest point on this segment
        proj_lat = p1[0] + t * (p2[0] - p1[0])
        proj_lon = p1[1] + t * (p2[1] - p1[1])

        d_seg = haversine_distance(lat, lon, proj_lat, proj_lon)
        min_dist = min(min_dist, d_seg)

    return min_dist


class AnomalyModel:
    def __init__(self, artifact_path: str = ""):
        self.version = "rules-v1"
        self.artifact_path = artifact_path
        self.bus_states = {}  # { busId: { last_timestamp, last_telemetry, stationary_start_time } }
        self.inactive_trip_states = {}  # { busId: { timestamps, last_alert_timestamp } }
        self.off_route_states = {}  # { busId: { count, window_start_ts, alerted } }
        self.telemetry_windows = {}  # { busId: [recent telemetry dicts] }
        # Isolation Forest model for behavioral anomaly detection (optional).
        self.isolation_model = None
        self.isolation_model_path = settings.isolation_forest_artifact_path
        try:
            # load an optional model artifact if present
            import joblib

            candidate = self.isolation_model_path
            if not os.path.isabs(candidate):
                candidate = os.path.abspath(candidate)
            if os.path.exists(candidate):
                self.isolation_model = joblib.load(candidate)
                self.isolation_model_path = candidate
                logger.info("Loaded isolation forest model from %s", candidate)
        except Exception:
            # model not available in this environment; continue with rule-based checks
            logger.debug("No isolation forest model loaded (optional)")

    def detect(self, telemetry: Dict[str, Any], route_geometry: List[Tuple[float, float]]) -> List[Dict[str, Any]]:
        alerts = []
        bus_id = telemetry["busId"]
        speed = telemetry.get("speed", 0.0)
        lat = telemetry.get("lat", 0.0)
        lon = telemetry.get("lon", 0.0)
        ts_str = telemetry.get("timestamp")
        route_id = telemetry.get("routeId")

        current_time = self._parse_timestamp(ts_str)

        # --- IsolationForest ML scoring (pre-rule, unsupervised) ---
        dist_to_route = distance_to_polyline(lat, lon, route_geometry) if route_geometry else 0.0
        prev_state = self.bus_states.get(bus_id, {})
        prev_heading = (prev_state.get("last_telemetry") or {}).get("heading", telemetry.get("heading", 0.0))
        curr_heading = telemetry.get("heading", 0.0)
        heading_delta = abs(curr_heading - prev_heading) % 360
        heading_delta = min(heading_delta, 360 - heading_delta)
        route_progress = telemetry.get("routeProgressPct", 0.0) or 0.0
        hour_of_day = datetime.now(timezone.utc).hour
        if self.artifact_path:
            speed_ms = speed / 3.6 if speed > 10 else speed  # convert km/h → m/s
            if_result = if_predict(
                speed_ms=speed_ms,
                distance_to_route_m=dist_to_route,
                heading_delta_deg=heading_delta,
                route_progress_pct=route_progress,
                hour_of_day=hour_of_day,
            )
            if if_result is not None:
                is_anomaly, if_score = if_result
                if is_anomaly:
                    alerts.append(self._create_alert(
                        bus_id, "ML_ANOMALY",
                        f"IsolationForest anomaly score {if_score:.3f}",
                        telemetry,
                        extra={"if_score": if_score},
                    ))

        # 1. Unrealistic Speed
        if speed > 120.0:
            alerts.append(self._create_alert(bus_id, "UNREALISTIC_SPEED", "Speed exceeded 120 km/h", telemetry))

        # 2. Inactive GPS
        if not route_id:
            alerts.append(self._create_alert(bus_id, "INACTIVE_GPS", "GPS received for inactive trip", telemetry))
            return alerts # Stop further checks if inactive

        # 3. Off-route deviation. Prefer Flink's CR1 classification when present,
        # and fall back to local geometry for backward compatibility.
        off_route, dist = self._off_route_status(telemetry, route_geometry)
        if off_route:
            alerts.append(self._create_alert(bus_id, "OFF_ROUTE", f"Bus deviated by {round(dist)}m from route", telemetry))
            persistent_alert = self._update_off_route_streak(bus_id, current_time, telemetry, dist)
            if persistent_alert:
                alerts.append(persistent_alert)
        else:
            self.off_route_states.pop(bus_id, None)

        # 4. Stationary Bus (>5 min at <2 km/h)
        state = self.bus_states.get(bus_id, {})
        if speed < 2.0:
            if "stationary_start_time" not in state:
                state["stationary_start_time"] = current_time
            elif current_time - state["stationary_start_time"] > 300: # 5 minutes
                alerts.append(self._create_alert(bus_id, "STATIONARY", "Bus stationary for over 5 minutes", telemetry))
        else:
            if "stationary_start_time" in state:
                del state["stationary_start_time"]

        state["last_timestamp"] = current_time
        state["last_telemetry"] = dict(telemetry)
        state["communication_loss_alerted"] = False
        self.bus_states[bus_id] = state

        # Behavioral anomaly detection via summary-vector -> IsolationForest
        behavioral_alert = self._detect_behavioral_anomaly(bus_id, telemetry)
        if behavioral_alert:
            alerts.append(behavioral_alert)

        return alerts

    def _detect_behavioral_anomaly(
        self,
        bus_id: str,
        telemetry: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        window = self.telemetry_windows.setdefault(bus_id, [])
        window.append(dict(telemetry))
        max_window_size = max(settings.sliding_window_size, settings.sliding_window_min_size)
        if len(window) > max_window_size:
            del window[:-max_window_size]

        if len(window) < settings.sliding_window_min_size:
            return None

        try:
            summary = build_summary_vector(window[-settings.sliding_window_size:])
            pred = self.predict_behavioral_anomaly(summary)
            if pred is not None and pred == -1:
                return self._create_alert(
                    bus_id,
                    "ERRATIC_DRIVING",
                    "Behavioral anomaly detected",
                    telemetry,
                    extra={"features": summary},
                )
        except Exception:
            logger.debug("Behavioral anomaly prediction skipped due to missing model or invalid window")

        return None

    def _off_route_status(
        self,
        telemetry: Dict[str, Any],
        route_geometry: List[Tuple[float, float]],
    ) -> tuple[bool, float]:
        if "offRoute" in telemetry:
            return bool(telemetry["offRoute"]), self._route_deviation_meters(telemetry)
        if "on_route" in telemetry:
            return not bool(telemetry["on_route"]), self._route_deviation_meters(telemetry)
        if "onRoute" in telemetry:
            return not bool(telemetry["onRoute"]), self._route_deviation_meters(telemetry)

        if not route_geometry:
            return False, 0.0

        dist = distance_to_polyline(telemetry.get("lat", 0.0), telemetry.get("lon", 0.0), route_geometry)
        return dist > settings.off_route_distance_threshold_m, dist

    def _route_deviation_meters(self, telemetry: Dict[str, Any]) -> float:
        for field in ("offRouteDistanceM", "routeDeviationMeters", "route_deviation_meters"):
            try:
                return float(telemetry.get(field, 0.0))
            except (TypeError, ValueError):
                continue
        return 0.0

    def _update_off_route_streak(
        self,
        bus_id: str,
        current_time: float,
        telemetry: Dict[str, Any],
        distance_m: float,
    ) -> Dict[str, Any] | None:
        state = self.off_route_states.get(bus_id)
        if (
            state is None
            or current_time - state["window_start_ts"] > settings.off_route_streak_window_seconds
        ):
            state = {"count": 0, "window_start_ts": current_time, "alerted": False}

        state["count"] += 1
        self.off_route_states[bus_id] = state

        if state["count"] < settings.persistent_off_route_threshold or state["alerted"]:
            return None

        state["alerted"] = True
        return self._create_alert(
            bus_id,
            "PERSISTENT_OFF_ROUTE",
            (
                "Bus remained off-route for "
                f"{state['count']} readings within {settings.off_route_streak_window_seconds}s"
            ),
            telemetry,
            extra={
                "streakCount": state["count"],
                "windowSeconds": settings.off_route_streak_window_seconds,
                "offRouteDistanceM": round(distance_m, 2),
            },
        )

    def predict_behavioral_anomaly(self, summary_vector: Dict[str, float]):
        """Return IsolationForest prediction if model available, else None.

        The IsolationForest convention: -1 => anomaly, 1 => normal.
        """
        if self.isolation_model is None:
            return None
        try:
            # model expects a 2D array-like
            features = [
                summary_vector.get("max_acceleration", 0.0),
                summary_vector.get("min_acceleration", 0.0),
                summary_vector.get("speed_variance", 0.0),
                summary_vector.get("heading_variance", 0.0),
                summary_vector.get("average_speed", 0.0),
                summary_vector.get("sample_count", 0.0),
            ]
            pred = self.isolation_model.predict([features])
            return int(pred[0])
        except Exception:
            logger.exception("Isolation forest prediction failed")
            return None

    def detect_inactive_trip_dlq(
        self,
        dlq_event: Dict[str, Any],
        now: datetime | None = None,
        threshold_count: int = 3,
        window_seconds: int = 60,
        cooldown_seconds: int = 300,
    ) -> List[Dict[str, Any]]:
        """Detect a device sending GPS while its driver has not started a trip."""
        if not self._is_inactive_trip_event(dlq_event):
            return []

        bus_id = self._extract_bus_id(dlq_event)
        if not bus_id:
            logger.warning("Ignoring INACTIVE_TRIP DLQ event without busId")
            return []

        event_ts = self._dlq_event_time(dlq_event, now)
        event_ts_seconds = event_ts.timestamp()
        state = self.inactive_trip_states.setdefault(
            bus_id,
            {"timestamps": [], "last_alert_timestamp": None},
        )

        cutoff = event_ts_seconds - window_seconds
        state["timestamps"] = [ts for ts in state["timestamps"] if ts >= cutoff]
        state["timestamps"].append(event_ts_seconds)

        recent_count = len(state["timestamps"])
        last_alert_timestamp = state.get("last_alert_timestamp")
        in_cooldown = (
            last_alert_timestamp is not None
            and event_ts_seconds - last_alert_timestamp < cooldown_seconds
        )

        if recent_count < threshold_count or in_cooldown:
            return []

        state["last_alert_timestamp"] = event_ts_seconds
        telemetry = self._extract_original_payload(dlq_event)
        return [
            self._create_alert(
                bus_id,
                "TRIP_NOT_STARTED_DEVICE_ACTIVE",
                "Device is sending GPS but no active trip exists",
                telemetry,
                source="transport-telemetry-dlq",
                extra={
                    "sourceReason": "INACTIVE_TRIP",
                    "dlqCount": recent_count,
                    "windowSeconds": window_seconds,
                },
            )
        ]

    def detect_communication_loss(
        self,
        now: datetime | None = None,
        threshold_seconds: int = 180,
    ) -> List[Dict[str, Any]]:
        """
        Detect buses that stopped sending telemetry.

        This runs from a periodic service task because no Kafka message arrives when
        a bus goes fully silent.
        """
        now_ts = (now or datetime.now(timezone.utc)).timestamp()
        alerts = []

        for bus_id, state in self.bus_states.items():
            last_timestamp = state.get("last_timestamp")
            last_telemetry = state.get("last_telemetry")
            already_alerted = state.get("communication_loss_alerted", False)

            if not last_timestamp or not last_telemetry or already_alerted:
                continue

            if now_ts - last_timestamp > threshold_seconds:
                alerts.append(
                    self._create_alert(
                        bus_id,
                        "COMMUNICATION_LOSS",
                        "No telemetry for over 3 minutes",
                        last_telemetry,
                    )
                )
                state["communication_loss_alerted"] = True

        return alerts

    def _parse_timestamp(self, ts_str: str | None) -> float:
        try:
            if ts_str and ts_str.endswith('Z'):
                ts_str = ts_str[:-1] + '+00:00'
            if ts_str:
                return datetime.fromisoformat(ts_str).timestamp()
        except Exception:
            logger.warning("Invalid telemetry timestamp: %s", ts_str)

        return datetime.now(timezone.utc).timestamp()

    def _dlq_event_time(self, dlq_event: Dict[str, Any], now: datetime | None) -> datetime:
        if now is not None:
            return now

        for field in ("received_at", "event_timestamp", "timestamp"):
            value = dlq_event.get(field)
            if not value:
                continue
            try:
                return self._parse_datetime(value)
            except ValueError:
                logger.warning("Invalid DLQ timestamp in %s: %s", field, value)

        return datetime.now(timezone.utc)

    def _parse_datetime(self, value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _is_inactive_trip_event(self, dlq_event: Dict[str, Any]) -> bool:
        error_type = str(
            dlq_event.get("error_type")
            or dlq_event.get("errorType")
            or ""
        ).upper()
        error_reason = str(
            dlq_event.get("error_reason")
            or dlq_event.get("reason")
            or ""
        ).upper()

        return error_type == "INACTIVE_TRIP" or "INACTIVE_TRIP" in error_reason

    def _extract_bus_id(self, dlq_event: Dict[str, Any]) -> str | None:
        bus_id = dlq_event.get("busId") or dlq_event.get("bus_id")
        if bus_id is not None:
            return str(bus_id)

        original_payload = self._extract_original_payload(dlq_event)
        bus_id = original_payload.get("busId") or original_payload.get("bus_id")
        return str(bus_id) if bus_id is not None else None

    def _extract_original_payload(self, dlq_event: Dict[str, Any]) -> Dict[str, Any]:
        original_payload = dlq_event.get("original_payload")
        if isinstance(original_payload, dict):
            return dict(original_payload)
        if isinstance(original_payload, str):
            try:
                parsed = json.loads(original_payload)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    def _create_alert(
        self,
        bus_id: str,
        type: str,
        message: str,
        telemetry: Dict[str, Any],
        *,
        source: str | None = None,
        extra: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        severity = "HIGH" if type in {"OFF_ROUTE", "PERSISTENT_OFF_ROUTE", "UNREALISTIC_SPEED"} else "MEDIUM"
        alert = {
            "busId": bus_id,
            "anomalyType": type,
            "severity": severity,
            "message": message,
            "tripId": telemetry.get("tripId"),
            "routeId": telemetry.get("routeId"),
            "location": {"lat": telemetry.get("lat"), "lon": telemetry.get("lon")},
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "modelVersion": self.version
        }
        if source:
            alert["source"] = source
        if extra:
            alert.update(extra)
        return alert
