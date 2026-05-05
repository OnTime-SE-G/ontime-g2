import threading
from datetime import datetime, timezone
from time import time


REJECTION_REASONS = (
    "JSON_PARSE",
    "MISSING_TIMESTAMP",
    "SCHEMA_VALIDATION",
    "GEO_BOUNDS",
    "DUPLICATE",
    "INACTIVE_TRIP",
    "TRIP_CACHE_REBUILDING",
    "RATE_LIMIT",
    "RATE_LIMIT_EVENT_TIME",
    "SEQUENCE_ERROR",
    "FUTURE_TIMESTAMP",
    "STALE_REPLAY",
)

REJECTION_REASON_SNAPSHOT_KEYS = {
    "JSON_PARSE": "messages_rejected_json",
    "MISSING_TIMESTAMP": "messages_rejected_missing_timestamp",
    "SCHEMA_VALIDATION": "messages_rejected_schema",
    "GEO_BOUNDS": "messages_rejected_geo",
    "DUPLICATE": "messages_rejected_duplicate",
    "INACTIVE_TRIP": "messages_rejected_inactive_trip",
    "TRIP_CACHE_REBUILDING": "messages_rejected_trip_cache_rebuilding",
    "RATE_LIMIT": "messages_rejected_rate_limit",
    "RATE_LIMIT_EVENT_TIME": "messages_rejected_rate_limit_event_time",
    "SEQUENCE_ERROR": "messages_rejected_sequence",
    "FUTURE_TIMESTAMP": "messages_rejected_future_timestamp",
    "STALE_REPLAY": "messages_rejected_stale_replay",
}


class MetricsCollector:
    """Thread-safe metrics collection for ingestion."""

    def __init__(self):
        self.messages_received = 0
        self.messages_validated = 0
        self.heartbeat_messages_received = 0
        self.heartbeat_messages_invalid = 0
        self.latest_heartbeat_by_bus: dict[str, datetime] = {}
        self.rejections_by_reason = {reason: 0 for reason in REJECTION_REASONS}

        self.start_time = time()
        self.last_message_time = 0.0

        self.kafka_broker_up = False
        self.mqtt_broker_up = False
        self.trip_cache_status = "unknown"
        self.active_trip_count = 0
        self.last_trip_lifecycle_time = None

        self._lock = threading.RLock()

    def increment_received(self):
        with self._lock:
            self.messages_received += 1
            self.last_message_time = time()

    def increment_validated(self):
        with self._lock:
            self.messages_validated += 1

    def record_heartbeat(self, *, bus_id: str, timestamp: datetime):
        with self._lock:
            self.heartbeat_messages_received += 1
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            self.latest_heartbeat_by_bus[bus_id] = timestamp.astimezone(timezone.utc)

    def increment_invalid_heartbeat(self):
        with self._lock:
            self.heartbeat_messages_invalid += 1

    def increment_rejected(self, error_type: str):
        with self._lock:
            if error_type in self.rejections_by_reason:
                self.rejections_by_reason[error_type] += 1

    def update_trip_cache(
        self,
        *,
        status: str,
        active_trip_count: int,
        last_lifecycle_timestamp: str | None,
    ):
        with self._lock:
            self.trip_cache_status = status
            self.active_trip_count = active_trip_count
            self.last_trip_lifecycle_time = last_lifecycle_timestamp

    def get_uptime_seconds(self) -> float:
        return time() - self.start_time

    def total_rejected(self) -> int:
        with self._lock:
            return sum(self.rejections_by_reason.values())

    def _legacy_rejection_snapshot(self) -> dict:
        return {
            snapshot_key: self.rejections_by_reason[reason]
            for reason, snapshot_key in REJECTION_REASON_SNAPSHOT_KEYS.items()
        }

    def get_snapshot(self) -> dict:
        with self._lock:
            now = datetime.now(timezone.utc)
            snapshot = {
                "messages_received": self.messages_received,
                "messages_validated": self.messages_validated,
                "heartbeat_messages_received": self.heartbeat_messages_received,
                "heartbeat_messages_invalid": self.heartbeat_messages_invalid,
                "latest_heartbeat_by_bus": {
                    bus_id: timestamp.isoformat()
                    for bus_id, timestamp in self.latest_heartbeat_by_bus.items()
                },
                "heartbeat_age_seconds_by_bus": {
                    bus_id: max(0.0, (now - timestamp).total_seconds())
                    for bus_id, timestamp in self.latest_heartbeat_by_bus.items()
                },
                "messages_rejected": self.total_rejected(),
                "rejections_by_reason": dict(self.rejections_by_reason),
                "uptime_seconds": self.get_uptime_seconds(),
                "kafka_broker_up": self.kafka_broker_up,
                "mqtt_broker_up": self.mqtt_broker_up,
                "trip_cache_status": self.trip_cache_status,
                "active_trip_count": self.active_trip_count,
                "last_trip_lifecycle_time": self.last_trip_lifecycle_time,
            }
            snapshot.update(self._legacy_rejection_snapshot())
            return snapshot


metrics = MetricsCollector()
