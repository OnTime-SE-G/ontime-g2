import logging
import math
from typing import List, Tuple, Dict, Any
from datetime import datetime, timezone
import json

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
    def __init__(self):
        self.version = "rules-v1"
        self.bus_states = {}  # { busId: { last_timestamp, last_telemetry, stationary_start_time } }
        self.inactive_trip_states = {}  # { busId: { timestamps, last_alert_timestamp } }

    def detect(self, telemetry: Dict[str, Any], route_geometry: List[Tuple[float, float]]) -> List[Dict[str, Any]]:
        alerts = []
        bus_id = telemetry["busId"]
        speed = telemetry.get("speed", 0.0)
        lat = telemetry.get("lat", 0.0)
        lon = telemetry.get("lon", 0.0)
        ts_str = telemetry.get("timestamp")
        route_id = telemetry.get("routeId")

        current_time = self._parse_timestamp(ts_str)

        # 1. Unrealistic Speed
        if speed > 120.0:
            alerts.append(self._create_alert(bus_id, "UNREALISTIC_SPEED", "Speed exceeded 120 km/h", telemetry))

        # 2. Inactive GPS
        if not route_id:
            alerts.append(self._create_alert(bus_id, "INACTIVE_GPS", "GPS received for inactive trip", telemetry))
            return alerts # Stop further checks if inactive

        # 3. Off-route deviation
        if route_geometry:
            dist = distance_to_polyline(lat, lon, route_geometry)
            if dist > 50.0:
                alerts.append(self._create_alert(bus_id, "OFF_ROUTE", f"Bus deviated by {round(dist)}m from route", telemetry))

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

        return alerts

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
        alert = {
            "busId": bus_id,
            "anomalyType": type,
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
