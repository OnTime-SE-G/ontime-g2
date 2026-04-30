# services/ingestion/metrics.py
# Thread-safe metrics collector for the Ingestion Service.
# Shared between mqtt_subscriber and health endpoints.

import threading
from time import time


class MetricsCollector:
    """Thread-safe metrics collection."""

    def __init__(self):
        self.messages_received = 0
        self.messages_validated = 0
        self.messages_rejected_json = 0
        self.messages_rejected_schema = 0
        self.messages_rejected_geo = 0
        self.messages_rejected_duplicate = 0
        self.messages_rejected_rate_limit = 0
        self.messages_rejected_sequence = 0

        self.start_time = time()
        self.last_message_time = 0.0

        self.kafka_broker_up = True
        self.mqtt_broker_up = True

        # Snapshot generation calls helper methods that also read counters,
        # so we use an RLock to keep those reads safe without deadlocking.
        self._lock = threading.RLock()

    def increment_received(self):
        """Increment messages_received counter."""
        with self._lock:
            self.messages_received += 1
            self.last_message_time = time()

    def increment_validated(self):
        """Increment messages_validated counter."""
        with self._lock:
            self.messages_validated += 1

    def increment_rejected(self, error_type: str):
        """Increment rejection counter based on error type."""
        with self._lock:
            if error_type == "JSON_PARSE":
                self.messages_rejected_json += 1
            elif error_type == "SCHEMA_VALIDATION":
                self.messages_rejected_schema += 1
            elif error_type == "GEO_BOUNDS":
                self.messages_rejected_geo += 1
            elif error_type == "DUPLICATE":
                self.messages_rejected_duplicate += 1
            elif error_type == "RATE_LIMIT":
                self.messages_rejected_rate_limit += 1
            elif error_type == "SEQUENCE_ERROR":
                self.messages_rejected_sequence += 1

    def get_uptime_seconds(self) -> float:
        """Get uptime in seconds."""
        return time() - self.start_time

    def total_rejected(self) -> int:
        """Get total rejected messages."""
        with self._lock:
            return (
                self.messages_rejected_json +
                self.messages_rejected_schema +
                self.messages_rejected_geo +
                self.messages_rejected_duplicate +
                self.messages_rejected_rate_limit +
                self.messages_rejected_sequence
            )

    def get_snapshot(self) -> dict:
        """Get a snapshot of all metrics (thread-safe)."""
        with self._lock:
            return {
                "messages_received": self.messages_received,
                "messages_validated": self.messages_validated,
                "messages_rejected": self.total_rejected(),
                "messages_rejected_json": self.messages_rejected_json,
                "messages_rejected_schema": self.messages_rejected_schema,
                "messages_rejected_geo": self.messages_rejected_geo,
                "messages_rejected_duplicate": self.messages_rejected_duplicate,
                "messages_rejected_rate_limit": self.messages_rejected_rate_limit,
                "messages_rejected_sequence": self.messages_rejected_sequence,
                "uptime_seconds": self.get_uptime_seconds(),
                "kafka_broker_up": self.kafka_broker_up,
                "mqtt_broker_up": self.mqtt_broker_up,
            }


# Global metrics instance
metrics = MetricsCollector()
