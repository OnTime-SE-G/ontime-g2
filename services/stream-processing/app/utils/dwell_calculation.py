"""
Dwell Time Calculation

Computes time spent at bus stops using stateful tracking of vehicle positions.
Maintains a cache of vehicle movements keyed by vehicle_id + trip_id.
"""

import logging
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class VehicleStopState:
    """Tracks vehicle state at a stop."""
    vehicle_id: str
    trip_id: str
    stop_id: str
    entry_time: datetime
    last_update: datetime = field(default_factory=datetime.utcnow)
    dwell_seconds: int = 0
    
    def update_dwell(self, current_time: datetime) -> int:
        """Update dwell time based on current time."""
        delta = current_time - self.entry_time
        self.dwell_seconds = int(delta.total_seconds())
        self.last_update = current_time
        return self.dwell_seconds


class DwellCalculator:
    """
    Calculates dwell times for vehicles at stops.
    
    Maintains a stateful cache of vehicle positions and computes:
    - dwell_current_sec: time spent at current stop
    - dwell_prev_sec: time spent at previous stop
    """
    
    def __init__(self, cache_ttl_seconds: int = 3600):
        """
        Initialize the calculator.
        
        Args:
            cache_ttl_seconds: TTL for cached stop states (default 1 hour)
        """
        self.cache_ttl_seconds = cache_ttl_seconds
        # Format: {(vehicle_id, trip_id): {"current": VehicleStopState, "previous": VehicleStopState}}
        self._state_cache: Dict[Tuple[str, str], Dict] = {}
        self._cleanup_counter = 0
    
    def record_vehicle_at_stop(
        self,
        vehicle_id: str,
        trip_id: str,
        stop_id: str,
        timestamp: datetime
    ) -> Tuple[int, Optional[int]]:
        """
        Record that a vehicle is at a stop.
        
        Returns:
            (dwell_current_sec, dwell_prev_sec)
            - dwell_current_sec: seconds at current stop (0 if just arrived)
            - dwell_prev_sec: seconds at previous stop (None if first stop)
        """
        key = (vehicle_id, trip_id)
        
        # Check if vehicle moved to a new stop
        if key in self._state_cache:
            cached = self._state_cache[key]
            current_state = cached.get("current")
            
            if current_state and current_state.stop_id != stop_id:
                # Vehicle moved to a new stop
                # Save current state as previous
                dwell_prev = current_state.dwell_seconds
                cached["previous"] = current_state
                
                # Create new current state
                new_state = VehicleStopState(
                    vehicle_id=vehicle_id,
                    trip_id=trip_id,
                    stop_id=stop_id,
                    entry_time=timestamp
                )
                cached["current"] = new_state
                dwell_current = 0
            else:
                # Still at the same stop, update dwell
                dwell_current = current_state.update_dwell(timestamp)
                prev_state = cached.get("previous")
                dwell_prev = prev_state.dwell_seconds if prev_state is not None else None
        else:
            # First time tracking this vehicle+trip
            new_state = VehicleStopState(
                vehicle_id=vehicle_id,
                trip_id=trip_id,
                stop_id=stop_id,
                entry_time=timestamp
            )
            self._state_cache[key] = {
                "current": new_state,
                "previous": None
            }
            dwell_current = 0
            dwell_prev = None
        
        # Periodic cleanup of old entries
        self._cleanup_counter += 1
        if self._cleanup_counter % 100 == 0:
            self._cleanup_expired_entries()
        
        return dwell_current, dwell_prev
    
    def _cleanup_expired_entries(self) -> None:
        """Remove cached entries older than TTL."""
        now = datetime.utcnow()
        expired_keys = []
        
        for key, cached in self._state_cache.items():
            current_state = cached.get("current")
            if current_state:
                age_seconds = (now - current_state.last_update).total_seconds()
                if age_seconds > self.cache_ttl_seconds:
                    expired_keys.append(key)
        
        for key in expired_keys:
            del self._state_cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired vehicle states")
    
    def get_vehicle_state(self, vehicle_id: str, trip_id: str) -> Optional[Dict]:
        """Get current cached state for a vehicle."""
        return self._state_cache.get((vehicle_id, trip_id))
    
    def clear_vehicle_state(self, vehicle_id: str, trip_id: str) -> None:
        """Clear cached state for a vehicle (e.g., when trip ends)."""
        key = (vehicle_id, trip_id)
        if key in self._state_cache:
            del self._state_cache[key]
            logger.debug(f"Cleared state for {vehicle_id} trip {trip_id}")


# Global instance
_default_calculator: Optional[DwellCalculator] = None


def get_dwell_calculator() -> DwellCalculator:
    """Get or create the default dwell calculator."""
    global _default_calculator
    if _default_calculator is None:
        _default_calculator = DwellCalculator()
    return _default_calculator
