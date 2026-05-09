"""Minimal PyFlink job template (scaffold).

This scaffold mirrors the CR1 event-driven source-of-truth pipeline without
requiring a running Flink cluster or the PyFlink package during import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Tuple

try:
    from pyflink.datastream import StreamExecutionEnvironment
except ImportError:  # pragma: no cover - import-safe scaffold for local tests
    StreamExecutionEnvironment = None


RAW_TOPIC = "transport-telemetry-raw"
CLEANED_TOPIC = "transport-telemetry-cleaned"
INVALID_TOPIC = "telemetry-invalid"
TRIP_LIFECYCLE_TOPIC = "trip.lifecycle"


@dataclass
class RuntimeCache:
    """In-memory view of the Flink-side startup cache.

    The production implementation should back this with RocksDB state. This
    dataclass makes the expected shape explicit for the scaffold.
    """

    routes: Dict[str, List[Tuple[float, float]]] = field(default_factory=dict)
    active_trips: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def classify_physics(event: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Classify a telemetry event into cleaned vs invalid.

    The scaffold uses simple physics checks only. Production Flink should
    replace this with route matching, trip state joins, and classification.
    """
    candidate = dict(event)
    lat = candidate.get("lat")
    lon = candidate.get("lon")
    speed = float(candidate.get("speed") or 0.0)

    if lat is None or lon is None:
        candidate["_invalid_reason"] = "MISSING_COORDINATES"
        return "invalid", candidate

    if speed > 120.0:
        candidate["_invalid_reason"] = "UNREALISTIC_SPEED"
        return "invalid", candidate

    candidate.setdefault("on_route", True)
    candidate.setdefault("physics_status", "accepted")
    return "cleaned", candidate


def enrich_with_trip_context(event: Dict[str, Any], cache: RuntimeCache) -> Dict[str, Any]:
    """Attach route/trip metadata when it exists in the scaffold cache."""
    candidate = dict(event)
    bus_id = candidate.get("busId") or candidate.get("bus_id")
    if bus_id is None:
        candidate.setdefault("on_route", False)
        candidate.setdefault("trip_status", "unknown")
        return candidate

    trip_state = cache.active_trips.get(str(bus_id))
    if trip_state:
        candidate.setdefault("tripId", trip_state.get("tripId"))
        candidate.setdefault("routeId", trip_state.get("routeId"))
        candidate.setdefault("trip_status", trip_state.get("status", "active"))
    else:
        candidate.setdefault("trip_status", "inactive")

    candidate.setdefault("on_route", True)
    return candidate


def route_lifecycle_event(event: Dict[str, Any], cache: RuntimeCache) -> None:
    """Update the cache from a trip.lifecycle event.

    Expected event fields include busId, tripId, routeId, event, and timestamp.
    """
    bus_id = event.get("busId") or event.get("bus_id")
    if bus_id is None:
        return

    event_type = str(event.get("event") or event.get("type") or "").upper()
    bus_key = str(bus_id)
    if event_type in {"TRIP_STARTED", "TRIP_ACTIVATED", "STARTED"}:
        cache.active_trips[bus_key] = {
            "tripId": event.get("tripId") or event.get("trip_id"),
            "routeId": event.get("routeId") or event.get("route_id"),
            "status": "active",
            "timestamp": event.get("timestamp"),
        }
    elif event_type in {"TRIP_ENDED", "TRIP_COMPLETED", "ENDED"}:
        cache.active_trips.pop(bus_key, None)


def main():
    if StreamExecutionEnvironment is None:
        print(
            "PyFlink is not installed. This scaffold defines the expected "
            "pipeline structure, topic names, and transformation helpers only."
        )
        return

    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)

    # Real deployment should:
    # 1. Consume RAW_TOPIC from Kafka.
    # 2. Consume TRIP_LIFECYCLE_TOPIC to keep RuntimeCache fresh.
    # 3. Hydrate route geometry at startup from Route/Fleet REST APIs.
    # 4. Classify each event with classify_physics() and enrich_with_trip_context().
    # 5. Emit to CLEANED_TOPIC or INVALID_TOPIC.
    print("PyFlink scaffold ready. Attach Kafka sources/sinks and execute on a cluster.")


if __name__ == "__main__":
    main()
