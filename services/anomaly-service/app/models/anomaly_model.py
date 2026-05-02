import logging
import math
from typing import List, Tuple, Dict, Any
from datetime import datetime

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
    """Calculate the shortest distance from a point to a polyline."""
    if not polyline:
        return float('inf')
        
    min_dist = float('inf')
    for p_lat, p_lon in polyline:
        d = haversine_distance(lat, lon, p_lat, p_lon)
        if d < min_dist:
            min_dist = d
    return min_dist

class AnomalyModel:
    def __init__(self):
        self.version = "rules-v1"
        self.bus_states = {}  # { busId: { last_timestamp, stationary_start_time } }

    def detect(self, telemetry: Dict[str, Any], route_geometry: List[Tuple[float, float]]) -> List[Dict[str, Any]]:
        alerts = []
        bus_id = telemetry["busId"]
        speed = telemetry.get("speed", 0.0)
        lat = telemetry.get("lat", 0.0)
        lon = telemetry.get("lon", 0.0)
        ts_str = telemetry.get("timestamp")
        route_id = telemetry.get("routeId")
        
        try:
            if ts_str.endswith('Z'):
                ts_str = ts_str[:-1] + '+00:00'
            current_time = datetime.fromisoformat(ts_str).timestamp()
        except:
            current_time = datetime.now().timestamp()

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

        # 5. Communication loss
        # Handled externally via a separate periodic check, but we update the last seen timestamp here
        if "last_timestamp" in state and current_time - state["last_timestamp"] > 180: # 3 mins
            alerts.append(self._create_alert(bus_id, "COMMUNICATION_LOSS", "No telemetry for over 3 minutes", telemetry))
            
        state["last_timestamp"] = current_time
        self.bus_states[bus_id] = state

        return alerts

    def _create_alert(self, bus_id: str, type: str, message: str, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "busId": bus_id,
            "anomalyType": type,
            "message": message,
            "tripId": telemetry.get("tripId"),
            "routeId": telemetry.get("routeId"),
            "location": {"lat": telemetry.get("lat"), "lon": telemetry.get("lon")},
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "modelVersion": self.version
        }
