import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from kafka import KafkaConsumer, TopicPartition
from pydantic import ValidationError

from schemas.trip_lifecycle import TripLifecycleEvent
from services.ingestion.app.config import settings
from services.ingestion.app.metrics import metrics

logger = logging.getLogger(__name__)

TripCacheStatus = Literal["rebuilding", "ready", "degraded", "stopped"]


@dataclass(frozen=True)
class ActiveTripInfo:
    bus_id: str
    trip_id: str
    route_id: str
    started_at: datetime
    last_lifecycle_timestamp: datetime


class ActiveTripCache:
    """Thread-safe in-memory active trip cache keyed by busId."""

    def __init__(self, *, initial_status: TripCacheStatus = "ready"):
        self._active_trips: dict[str, ActiveTripInfo] = {}
        self._status: TripCacheStatus = initial_status
        self._last_lifecycle_timestamp: datetime | None = None
        self._lock = threading.RLock()
        self._publish_metrics()

    @property
    def status(self) -> TripCacheStatus:
        with self._lock:
            return self._status

    @property
    def is_ready(self) -> bool:
        return self.status == "ready"

    @property
    def is_rebuilding(self) -> bool:
        return self.status == "rebuilding"

    def mark_rebuilding(self) -> None:
        self._set_status("rebuilding")

    def mark_ready(self) -> None:
        self._set_status("ready")

    def mark_degraded(self) -> None:
        self._set_status("degraded")

    def mark_stopped(self) -> None:
        self._set_status("stopped")

    def _set_status(self, status: TripCacheStatus) -> None:
        with self._lock:
            self._status = status
            self._publish_metrics_locked()

    def apply_event(self, event: TripLifecycleEvent) -> None:
        with self._lock:
            self._last_lifecycle_timestamp = event.timestamp

            if event.event == "TRIP_STARTED":
                self._active_trips[event.bus_id] = ActiveTripInfo(
                    bus_id=event.bus_id,
                    trip_id=event.trip_id,
                    route_id=event.route_id,
                    started_at=event.timestamp,
                    last_lifecycle_timestamp=event.timestamp,
                )
                self._publish_metrics_locked()
                return

            if event.event == "TRIP_ENDED":
                current = self._active_trips.get(event.bus_id)
                if current and current.trip_id == event.trip_id:
                    del self._active_trips[event.bus_id]
                self._publish_metrics_locked()

    def get_active_trip(self, bus_id: str) -> ActiveTripInfo | None:
        with self._lock:
            return self._active_trips.get(bus_id)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "status": self._status,
                "active_trip_count": len(self._active_trips),
                "last_lifecycle_timestamp": (
                    self._last_lifecycle_timestamp.isoformat()
                    if self._last_lifecycle_timestamp
                    else None
                ),
            }

    def _publish_metrics(self) -> None:
        with self._lock:
            self._publish_metrics_locked()

    def _publish_metrics_locked(self) -> None:
        metrics.update_trip_cache(
            status=self._status,
            active_trip_count=len(self._active_trips),
            last_lifecycle_timestamp=(
                self._last_lifecycle_timestamp.isoformat()
                if self._last_lifecycle_timestamp
                else None
            ),
        )


def decode_trip_lifecycle_event(raw_value: bytes | str | dict) -> TripLifecycleEvent:
    if isinstance(raw_value, bytes):
        payload = json.loads(raw_value.decode("utf-8"))
    elif isinstance(raw_value, str):
        payload = json.loads(raw_value)
    else:
        payload = raw_value

    return TripLifecycleEvent.model_validate(payload)


class TripLifecycleConsumer:
    """Background Kafka consumer that keeps ActiveTripCache current."""

    def __init__(
        self,
        cache: ActiveTripCache,
        *,
        bootstrap_servers: str | None = None,
        topic: str | None = None,
        group_id: str | None = None,
        rebuild_timeout_seconds: float | None = None,
    ):
        self.cache = cache
        self.bootstrap_servers = bootstrap_servers or settings.kafka_broker_url
        self.topic = topic or settings.kafka_trip_lifecycle_topic
        self.group_id = group_id or settings.trip_cache_consumer_group
        self.rebuild_timeout_seconds = (
            rebuild_timeout_seconds
            if rebuild_timeout_seconds is not None
            else settings.trip_cache_rebuild_timeout_seconds
        )
        self._consumer: KafkaConsumer | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        self.cache.mark_rebuilding()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._consumer is not None:
            self._consumer.close()
        self.cache.mark_stopped()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        try:
            self._consumer = self._create_consumer()
            self._prepare_rebuild_offsets()
            self._consume_rebuild_window()
            self.cache.mark_ready()
            self._consume_forever()
        except Exception:
            logger.exception("Trip lifecycle consumer failed")
            self.cache.mark_degraded()
        finally:
            if self._consumer is not None:
                self._consumer.close()

    def _create_consumer(self) -> KafkaConsumer:
        return KafkaConsumer(
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            consumer_timeout_ms=int(self.rebuild_timeout_seconds * 1000),
            value_deserializer=lambda value: value,
        )

    def _prepare_rebuild_offsets(self) -> None:
        if self._consumer is None:
            return

        partitions = self._consumer.partitions_for_topic(self.topic)
        if partitions is None:
            logger.warning(
                "No Kafka partitions found for %s; subscribing normally until topic exists",
                self.topic,
            )
            self._consumer.subscribe([self.topic])
            return

        topic_partitions = [
            TopicPartition(self.topic, partition) for partition in sorted(partitions)
        ]
        self._consumer.assign(topic_partitions)
        self._consumer.seek_to_beginning(*topic_partitions)

    def _consume_rebuild_window(self) -> None:
        if self._consumer is None:
            return

        for message in self._consumer:
            self._apply_raw_event(message.value)
            if self._stop_event.is_set():
                return

    def _consume_forever(self) -> None:
        if self._consumer is None:
            return

        while not self._stop_event.is_set():
            records = self._consumer.poll(timeout_ms=1000)
            for messages in records.values():
                for message in messages:
                    self._apply_raw_event(message.value)

    def _apply_raw_event(self, raw_value: bytes) -> None:
        try:
            event = decode_trip_lifecycle_event(raw_value)
        except (json.JSONDecodeError, UnicodeDecodeError, ValidationError):
            logger.warning("Ignoring invalid trip lifecycle event", exc_info=True)
            return

        self.cache.apply_event(event)
