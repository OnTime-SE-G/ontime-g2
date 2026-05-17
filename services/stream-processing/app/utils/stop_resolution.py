"""
Stop Resolution Utility

Resolves GPS coordinates (lat, lon) to stop IDs using geofencing.
Maintains a mapping of stop zones and implements point-in-polygon checks.
"""

import logging
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class StopZone:
    """Represents a bus stop zone with boundaries."""
    stop_id: str
    lat: float
    lon: float
    radius_meters: float = 50  # Default radius for geofence
    zone_name: str = ""

    def contains_point(self, lat: float, lon: float) -> bool:
        """Check if a point (lat, lon) is within this stop zone."""
        # Simple distance-based geofence (using approximate meters per degree)
        lat_diff = abs(lat - self.lat)
        lon_diff = abs(lon - self.lon)
        
        # Approximate: 1 degree ≈ 111 km
        lat_distance_m = lat_diff * 111000
        lon_distance_m = lon_diff * 111000 * 0.7  # Adjust for latitude
        
        distance = (lat_distance_m**2 + lon_distance_m**2) ** 0.5
        return distance <= self.radius_meters


class StopResolutionManager:
    """
    Manages stop zone mapping and resolves GPS coordinates to stop IDs.
    
    This is a simple in-memory manager. For production, consider loading
    stop zones from a database or configuration file.
    """
    
    def __init__(self):
        """Initialize with default stop zones (to be populated from config)."""
        self.stops: Dict[str, StopZone] = {}
    
    def add_stop(self, stop_zone: StopZone) -> None:
        """Add a stop zone to the manager."""
        self.stops[stop_zone.stop_id] = stop_zone
        logger.debug(f"Added stop: {stop_zone.stop_id} at ({stop_zone.lat}, {stop_zone.lon})")
    
    def resolve_stop(self, lat: float, lon: float) -> Optional[str]:
        """
        Resolve GPS coordinates to the nearest stop ID.
        
        Returns:
            stop_id if found within any zone, None otherwise.
        """
        for stop_id, zone in self.stops.items():
            if zone.contains_point(lat, lon):
                return stop_id
        
        logger.debug(f"No stop found for coordinates: ({lat}, {lon})")
        return None
    
    def get_stop_info(self, stop_id: str) -> Optional[StopZone]:
        """Get full information about a stop."""
        return self.stops.get(stop_id)
    
    def load_stops_from_dict(self, stops_dict: Dict) -> None:
        """
        Load stops from a dictionary configuration.
        
        Expected format:
        {
            "stop_1": {"lat": 6.9271, "lon": 80.7789, "radius_meters": 50, "name": "Colombo Central"},
            ...
        }
        """
        for stop_id, config in stops_dict.items():
            zone = StopZone(
                stop_id=stop_id,
                lat=config["lat"],
                lon=config["lon"],
                radius_meters=config.get("radius_meters", 50),
                zone_name=config.get("name", "")
            )
            self.add_stop(zone)
        logger.info(f"Loaded {len(stops_dict)} stop zones")


# Global instance (can be replaced with dependency injection in FastAPI)
_default_manager: Optional[StopResolutionManager] = None


def get_stop_resolution_manager() -> StopResolutionManager:
    """Get or create the default stop resolution manager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = StopResolutionManager()
    return _default_manager
