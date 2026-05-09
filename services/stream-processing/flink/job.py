"""Minimal PyFlink job template (scaffold).

This scaffold mirrors the CR1 event-driven source-of-truth pipeline without
requiring a running Flink cluster or the PyFlink package during import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple, Optional
import math

import httpx

try:
    from .config import settings
except ImportError:  # pragma: no cover - allows direct-file test loading
    import sys

    current_dir = Path(__file__).resolve().parent
    if str(current_dir) not in sys.path:
        sys.path.append(str(current_dir))
    from config import settings

try:
    from pyflink.datastream import StreamExecutionEnvironment
    from pyflink.datastream.connectors.kafka import (
        KafkaSource,
        KafkaSink,
        KafkaOffsetsInitializer,
        KafkaRecordSerializationSchema,
    )
    from pyflink.datastream.functions import SimpleStringSchema
except ImportError:  # pragma: no cover - import-safe scaffold for local tests
    StreamExecutionEnvironment = None
    KafkaSource = None
    KafkaSink = None
    KafkaOffsetsInitializer = None
    KafkaRecordSerializationSchema = None
    SimpleStringSchema = None

# Optional external libs used for sinks (import-safe)
try:
    import redis as redis_module
except Exception:  # pragma: no cover - redis optional
    redis_module = None

try:
    from influxdb_client import InfluxDBClient, Point
except Exception:  # pragma: no cover - influx optional
    InfluxDBClient = None
    Point = None


RAW_TOPIC = settings.kafka_raw_topic
CLEANED_TOPIC = settings.kafka_cleaned_topic
INVALID_TOPIC = settings.kafka_invalid_topic
TRIP_LIFECYCLE_TOPIC = settings.kafka_trip_lifecycle_topic
DEFAULT_HTTP_TIMEOUT_SECONDS = 5.0


@dataclass
class RuntimeCache:
    """In-memory view of the Flink-side startup cache.

    The production implementation should back this with RocksDB state. This
    dataclass makes the expected shape explicit for the scaffold.
    """

    routes: Dict[str, List[Tuple[float, float]]] = field(default_factory=dict)
    active_trips: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def _coerce_route_points(route_payload: Dict[str, Any]) -> List[Tuple[float, float]]:
    """Convert a route payload into a list of (lat, lon) tuples.

    Supports a few likely shapes so the scaffold remains useful while service
    APIs evolve.
    """
    points = (
        route_payload.get("polyline")
        or route_payload.get("geometry")
        or route_payload.get("points")
        or []
    )
    normalized: List[Tuple[float, float]] = []
    for point in points:
        if isinstance(point, dict):
            lat = point.get("lat")
            lon = point.get("lon")
            if lat is None:
                lat = point.get("latitude")
            if lon is None:
                lon = point.get("longitude")
            if lat is None or lon is None:
                continue
            normalized.append((float(lat), float(lon)))
            continue

        if isinstance(point, (list, tuple)) and len(point) >= 2:
            normalized.append((float(point[0]), float(point[1])))

    return normalized


def parse_route_cache_response(payload: Any) -> Dict[str, List[Tuple[float, float]]]:
    """Parse route-service response into route_id -> polyline points."""
    routes: Dict[str, List[Tuple[float, float]]] = {}

    candidates: Iterable[Any]
    if isinstance(payload, dict):
        if isinstance(payload.get("items"), list):
            candidates = payload["items"]
        elif isinstance(payload.get("routes"), list):
            candidates = payload["routes"]
        else:
            candidates = [payload]
    elif isinstance(payload, list):
        candidates = payload
    else:
        return routes

    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        route_id = entry.get("routeId") or entry.get("route_id") or entry.get("id")
        if route_id is None:
            continue
        points = _coerce_route_points(entry)
        if points:
            routes[str(route_id)] = points

    return routes


def parse_active_trip_cache_response(payload: Any) -> Dict[str, Dict[str, Any]]:
    """Parse fleet-service response into bus_id -> active trip state."""
    active: Dict[str, Dict[str, Any]] = {}

    candidates: Iterable[Any]
    if isinstance(payload, dict):
        if isinstance(payload.get("items"), list):
            candidates = payload["items"]
        elif isinstance(payload.get("activeTrips"), list):
            candidates = payload["activeTrips"]
        else:
            candidates = [payload]
    elif isinstance(payload, list):
        candidates = payload
    else:
        return active

    for entry in candidates:
        if not isinstance(entry, dict):
            continue

        bus_id = entry.get("busId") or entry.get("bus_id")
        trip_id = entry.get("tripId") or entry.get("trip_id")
        route_id = entry.get("routeId") or entry.get("route_id")
        if bus_id is None or trip_id is None:
            continue

        active[str(bus_id)] = {
            "tripId": trip_id,
            "routeId": route_id,
            "status": "active",
            "timestamp": entry.get("timestamp"),
        }

    return active


def fetch_startup_cache(
    route_service_url: str,
    fleet_service_url: str,
    timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> RuntimeCache:
    """Fetch startup cache snapshots from route and fleet services.

    Network failures are tolerated so Flink can still start and rely on
    `trip.lifecycle` events to progressively warm state.
    """
    cache = RuntimeCache()
    timeout = httpx.Timeout(timeout_seconds)

    with httpx.Client(timeout=timeout) as client:
        try:
            route_response = client.get(route_service_url)
            route_response.raise_for_status()
            cache.routes = parse_route_cache_response(route_response.json())
        except Exception:
            cache.routes = {}

        try:
            fleet_response = client.get(fleet_service_url)
            fleet_response.raise_for_status()
            cache.active_trips = parse_active_trip_cache_response(fleet_response.json())
        except Exception:
            cache.active_trips = {}

    return cache


def _haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # Haversine formula to compute distance between two lat/lon points in meters
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def classify_physics(event: Dict[str, Any], cache: Optional[RuntimeCache] = None) -> Tuple[str, Dict[str, Any]]:
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

    # Default: assume on_route unless route-aware cache indicates otherwise.
    on_route = True
    deviation_meters: Optional[float] = None
    try:
        threshold = float(settings.route_deviation_threshold_meters)
    except Exception:
        threshold = 50.0

    # If a runtime cache with routes is provided, compute nearest distance
    # to the declared route (if present) or to any known route as a fallback.
    route_id = candidate.get("routeId") or candidate.get("route_id")
    routes_to_check: Dict[str, List[Tuple[float, float]]] = {}
    if cache is not None:
        routes_to_check = cache.routes or {}

    if routes_to_check:
        candidates = []
        if route_id and str(route_id) in routes_to_check:
            candidates = [routes_to_check[str(route_id)]]
        else:
            # fallback: check all routes (cheap in scaffold; production should narrow)
            candidates = list(routes_to_check.values())

        nearest = None
        for poly in candidates:
            for (rlat, rlon) in poly:
                try:
                    dist = _haversine_distance_meters(float(lat), float(lon), float(rlat), float(rlon))
                except Exception:
                    continue
                if nearest is None or dist < nearest:
                    nearest = dist

        if nearest is not None:
            deviation_meters = float(nearest)
            on_route = deviation_meters <= threshold

    candidate.setdefault("on_route", on_route)
    if deviation_meters is not None:
        candidate.setdefault("route_deviation_meters", round(deviation_meters, 2))

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


def decode_event_payload(value: Any) -> Optional[Dict[str, Any]]:
    """Decode a raw JSON payload into a dictionary when possible."""
    if isinstance(value, dict):
        return dict(value)

    if isinstance(value, str):
        try:
            payload = json.loads(value)
        except Exception:
            return None
        if isinstance(payload, dict):
            return payload

    return None


def classify_event_record(value: Any, cache: Optional[RuntimeCache] = None) -> Dict[str, Any]:
    """Classify a raw Kafka record and return a kind/payload wrapper.

    This keeps the CR1 pipeline wiring simple while still exposing a pure,
    testable transformation surface for integration tests.
    """
    payload = decode_event_payload(value)
    if payload is None:
        return {"kind": "invalid", "payload": {"_invalid_reason": "MALFORMED_JSON"}}

    kind, candidate = classify_physics(payload, cache)
    if kind == "cleaned" and cache is not None:
        candidate = enrich_with_trip_context(candidate, cache)

    return {"kind": kind, "payload": candidate}


def apply_lifecycle_event(value: Any, cache: RuntimeCache) -> Any:
    """Update the in-memory cache from a lifecycle record and return the input unchanged."""
    payload = decode_event_payload(value)
    if payload is not None:
        route_lifecycle_event(payload, cache)
    return value


def publish_cleaned_event(payload: Dict[str, Any], redis_sink: Any = None, influx_sink: Any = None) -> Dict[str, Any]:
    """Fan out a cleaned event to the side-effect sinks used by CR1."""
    if redis_sink is not None:
        redis_sink.publish(payload)

    if influx_sink is not None:
        influx_sink.write("telemetry", payload)

    return payload


def build_raw_telemetry_source() -> KafkaSource:
    """Build a Kafka source for raw telemetry topic.

    Consumes JSON-encoded telemetry events from the ingestion service and
    initializes from the earliest offset (or committed offset if group has prior progress).
    """
    if KafkaSource is None:
        raise RuntimeError("PyFlink is not available in this environment.")

    return (
        KafkaSource.builder()
        .set_bootstrap_servers(settings.kafka_broker_url)
        .set_topics(settings.kafka_raw_topic)
        .set_group_id(settings.kafka_raw_consumer_group)
        .set_starting_offsets(KafkaOffsetsInitializer.earliest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )


def build_lifecycle_event_source() -> KafkaSource:
    """Build a Kafka source for trip lifecycle events.

    Consumes JSON-encoded lifecycle events (trip start/end) and initializes
    from the earliest offset to ensure cache warmup on restart.
    """
    if KafkaSource is None:
        raise RuntimeError("PyFlink is not available in this environment.")

    return (
        KafkaSource.builder()
        .set_bootstrap_servers(settings.kafka_broker_url)
        .set_topics(settings.kafka_trip_lifecycle_topic)
        .set_group_id(settings.kafka_lifecycle_consumer_group)
        .set_starting_offsets(KafkaOffsetsInitializer.earliest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )


def build_cleaned_telemetry_sink() -> KafkaSink:
    """Build a Kafka sink for physics-validated telemetry.

    Emits events that pass physics validation (speed, coordinates, etc.)
    to the cleaned topic with AT_LEAST_ONCE delivery semantics.
    Events may still be behaviorally anomalous but are kept in the
    cleaned stream with metadata flags (on_route, physics_status, etc.).
    """
    if KafkaSink is None:
        raise RuntimeError("PyFlink is not available in this environment.")

    return (
        KafkaSink.builder()
        .set_bootstrap_servers(settings.kafka_broker_url)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(settings.kafka_cleaned_topic)
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        )
        .set_delivery_guarantee("AT_LEAST_ONCE")
        .build()
    )


def build_invalid_telemetry_sink() -> KafkaSink:
    """Build a Kafka sink for physics-invalid telemetry.

    Emits events that fail physics validation (missing coordinates,
    unrealistic speed, etc.) to the invalid topic for DLQ handling,
    diagnostics, and offline analysis.
    """
    if KafkaSink is None:
        raise RuntimeError("PyFlink is not available in this environment.")

    return (
        KafkaSink.builder()
        .set_bootstrap_servers(settings.kafka_broker_url)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(settings.kafka_invalid_topic)
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        )
        .set_delivery_guarantee("AT_LEAST_ONCE")
        .build()
    )


def build_redis_live_sink():
    """Build a Redis live sink wrapper that publishes cleaned telemetry to a channel.

    Returns a small wrapper object with a `publish(value: dict)` method.
    """
    if redis_module is None:
        raise RuntimeError("redis library is not available in this environment.")

    client = redis_module.Redis(host=settings.redis_host, port=settings.redis_port)

    class RedisSinkWrapper:
        def __init__(self, redis_client, channel):
            self._redis = redis_client
            self._channel = channel

        def publish(self, value: Dict[str, Any]):
            import json

            try:
                self._redis.publish(self._channel, json.dumps(value))
            except Exception:
                # In scaffold mode, don't propagate Redis errors.
                pass

    return RedisSinkWrapper(client, settings.redis_live_channel)


def build_influx_history_sink():
    """Build an InfluxDB write helper used to persist cleaned telemetry points.

    Returns a wrapper with `write(measurement: str, data: dict)`.
    """
    if InfluxDBClient is None:
        raise RuntimeError("influxdb-client is not available in this environment.")

    client = InfluxDBClient(url=settings.influxdb_url, token=settings.influxdb_token, org=settings.influxdb_org)
    write_api = client.write_api()

    class InfluxSinkWrapper:
        def __init__(self, write_api, bucket, org):
            self._write_api = write_api
            self._bucket = bucket
            self._org = org

        def write(self, measurement: str, data: Dict[str, Any]):
            p = Point(measurement)
            for k, v in data.items():
                try:
                    if isinstance(v, (int, float)):
                        p.field(k, v)
                    else:
                        p.tag(k, str(v))
                except Exception:
                    # best-effort
                    p.tag(k, str(v))
            try:
                self._write_api.write(bucket=settings.influxdb_bucket, org=settings.influxdb_org, record=p)
            except Exception:
                # swallow in scaffold mode
                pass

    return InfluxSinkWrapper(write_api, settings.influxdb_bucket, settings.influxdb_org)


def main():
    if StreamExecutionEnvironment is None:
        print(
            "PyFlink is not installed. This scaffold defines the expected "
            "pipeline structure, topic names, and transformation helpers only."
        )
        return

    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(settings.flink_parallelism)

    cache = fetch_startup_cache(
        settings.route_service_cache_url,
        settings.fleet_service_active_trips_url,
        settings.startup_cache_timeout_seconds,
    )
    print(
        "Startup cache loaded: "
        f"routes={len(cache.routes)} active_trips={len(cache.active_trips)}"
    )

    # Build Kafka sources for raw telemetry and lifecycle events.
    raw_source = build_raw_telemetry_source()
    lifecycle_source = build_lifecycle_event_source()

    # Build Kafka sinks for classified telemetry.
    cleaned_sink = build_cleaned_telemetry_sink()
    invalid_sink = build_invalid_telemetry_sink()
    redis_sink = build_redis_live_sink()
    influx_sink = build_influx_history_sink()

    # Add sources to the environment and create streams.
    raw_stream = env.add_source(raw_source).name("raw-telemetry-source")
    lifecycle_stream = env.add_source(lifecycle_source).name("lifecycle-events-source")

    classified_stream = raw_stream.map(lambda value: classify_event_record(value, cache)).name(
        "raw-telemetry-classifier"
    )

    lifecycle_stream.map(lambda value: apply_lifecycle_event(value, cache)).name(
        "lifecycle-cache-updater"
    )

    cleaned_stream = classified_stream.filter(lambda item: item["kind"] == "cleaned").map(
        lambda item: item["payload"]
    ).name("cleaned-telemetry-stream")
    invalid_stream = classified_stream.filter(lambda item: item["kind"] == "invalid").map(
        lambda item: item["payload"]
    ).name("invalid-telemetry-stream")

    cleaned_stream.map(lambda payload: publish_cleaned_event(payload, redis_sink, influx_sink)).name(
        "redis-influx-side-effects"
    )
    cleaned_stream.map(lambda payload: json.dumps(payload)).sink_to(cleaned_sink).name(
        "cleaned-kafka-sink"
    )
    invalid_stream.map(lambda payload: json.dumps(payload)).sink_to(invalid_sink).name(
        "invalid-kafka-sink"
    )

    print(
        "Kafka sources configured: "
        f"raw_topic={settings.kafka_raw_topic} "
        f"lifecycle_topic={settings.kafka_trip_lifecycle_topic}"
    )

    print(
        "Kafka sinks configured: "
        f"cleaned_topic={settings.kafka_cleaned_topic} "
        f"invalid_topic={settings.kafka_invalid_topic}"
    )

    env.execute("OnTime CR1 Telemetry Processing")


if __name__ == "__main__":
    main()
