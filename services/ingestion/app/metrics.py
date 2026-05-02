import threading
from time import time


class MetricsCollector:
    """Thread-safe metrics collection for ingestion."""

    def __init__(self):
        self.messages_received = 0
        self.messages_validated = 0
        self.messages_rejected_json = 0
        self.messages_rejected_missing_timestamp = 0
        self.messages_rejected_schema = 0
        self.messages_rejected_geo = 0
        self.messages_rejected_duplicate = 0
        self.messages_rejected_rate_limit = 0
        self.messages_rejected_rate_limit_event_time = 0
        self.messages_rejected_sequence = 0
        self.messages_rejected_future_timestamp = 0
        self.messages_rejected_stale_replay = 0

        self.start_time = time()
        self.last_message_time = 0.0

        self.kafka_broker_up = False
        self.mqtt_broker_up = False

        self._lock = threading.RLock()

    def increment_received(self):
        with self._lock:
            self.messages_received += 1
            self.last_message_time = time()

    def increment_validated(self):
        with self._lock:
            self.messages_validated += 1

    def increment_rejected(self, error_type: str):
        with self._lock:
            if error_type == "JSON_PARSE":
                self.messages_rejected_json += 1
            elif error_type == "MISSING_TIMESTAMP":
                self.messages_rejected_missing_timestamp += 1
            elif error_type == "SCHEMA_VALIDATION":
                self.messages_rejected_schema += 1
            elif error_type == "GEO_BOUNDS":
                self.messages_rejected_geo += 1
            elif error_type == "DUPLICATE":
                self.messages_rejected_duplicate += 1
            elif error_type == "RATE_LIMIT":
                self.messages_rejected_rate_limit += 1
            elif error_type == "RATE_LIMIT_EVENT_TIME":
                self.messages_rejected_rate_limit_event_time += 1
            elif error_type == "SEQUENCE_ERROR":
                self.messages_rejected_sequence += 1
            elif error_type == "FUTURE_TIMESTAMP":
                self.messages_rejected_future_timestamp += 1
            elif error_type == "STALE_REPLAY":
                self.messages_rejected_stale_replay += 1

    def get_uptime_seconds(self) -> float:
        return time() - self.start_time

    def total_rejected(self) -> int:
        with self._lock:
            return (
                self.messages_rejected_json
                + self.messages_rejected_missing_timestamp
                + self.messages_rejected_schema
                + self.messages_rejected_geo
                + self.messages_rejected_duplicate
                + self.messages_rejected_rate_limit
                + self.messages_rejected_rate_limit_event_time
                + self.messages_rejected_sequence
                + self.messages_rejected_future_timestamp
                + self.messages_rejected_stale_replay
            )

    def get_snapshot(self) -> dict:
        with self._lock:
            return {
                "messages_received": self.messages_received,
                "messages_validated": self.messages_validated,
                "messages_rejected": self.total_rejected(),
                "messages_rejected_json": self.messages_rejected_json,
                "messages_rejected_missing_timestamp": self.messages_rejected_missing_timestamp,
                "messages_rejected_schema": self.messages_rejected_schema,
                "messages_rejected_geo": self.messages_rejected_geo,
                "messages_rejected_duplicate": self.messages_rejected_duplicate,
                "messages_rejected_rate_limit": self.messages_rejected_rate_limit,
                "messages_rejected_rate_limit_event_time": (
                    self.messages_rejected_rate_limit_event_time
                ),
                "messages_rejected_sequence": self.messages_rejected_sequence,
                "messages_rejected_future_timestamp": self.messages_rejected_future_timestamp,
                "messages_rejected_stale_replay": self.messages_rejected_stale_replay,
                "uptime_seconds": self.get_uptime_seconds(),
                "kafka_broker_up": self.kafka_broker_up,
                "mqtt_broker_up": self.mqtt_broker_up,
            }


metrics = MetricsCollector()
