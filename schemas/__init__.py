# schemas/__init__.py
# Shared Pydantic data contracts for the OnTime platform.
# All services and scripts import canonical models from here.

from .bus_status import BusLifecycleState, BusStatusMessage
from .geo_config import CoordinateBounds, SRI_LANKA_BOUNDS
from .gps import GPSMessage

__all__ = [
    "BusLifecycleState",
    "BusStatusMessage",
    "CoordinateBounds",
    "GPSMessage",
    "SRI_LANKA_BOUNDS",
]
