import json
import logging
from datetime import datetime, timezone

from kafka import KafkaProducer

from schemas.gps import GPSMessage
from services.ingestion.app.config import settings

logger = logging.getLogger(__name__)


def _as_utc_isoformat(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _parse_event_timestamp(value) -> str | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return _as_utc_isoformat(value)

    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
        except (OSError, OverflowError, ValueError):
            return None

    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return _as_utc_isoformat(parsed)

    return None


def _bus_id_from_topic(source_topic: str) -> str | None:
    topic_parts = source_topic.split("/")
    if len(topic_parts) >= 3 and topic_parts[0] == "transport" and topic_parts[1] == "bus":
        return topic_parts[2] or None
    return None


def _extract_dlq_metadata(raw_payload: bytes, source_topic: str) -> dict:
    metadata = {
        "busId": _bus_id_from_topic(source_topic),
        "tripId": None,
        "event_timestamp": None,
    }

    try:
        parsed = json.loads(raw_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return metadata

    if not isinstance(parsed, dict):
        return metadata

    bus_id = parsed.get("busId") or parsed.get("bus_id")
    if bus_id is not None:
        metadata["busId"] = str(bus_id)

    trip_id = parsed.get("tripId") or parsed.get("trip_id")
    if trip_id is not None:
        metadata["tripId"] = str(trip_id)

    metadata["event_timestamp"] = _parse_event_timestamp(parsed.get("timestamp"))
    return metadata


class TelemetryProducer:
    def __init__(self):
        self.producer = KafkaProducer(
            bootstrap_servers=settings.kafka_broker_url,
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
            key_serializer=lambda key: str(key).encode("utf-8") if key else None,
            acks="all",
        )
        self.raw_topic = settings.kafka_raw_topic
        self.dlq_topic = settings.kafka_dlq_topic
        logger.info("Initialized Kafka producer for %s", settings.kafka_broker_url)

    def publish_valid(self, message: GPSMessage):
        """Publish a valid GPS message to the raw telemetry topic."""
        payload = message.model_dump(by_alias=True)
        if "timestamp" in payload and isinstance(payload["timestamp"], datetime):
            payload["timestamp"] = payload["timestamp"].isoformat()

        self.producer.send(topic=self.raw_topic, key=message.bus_id, value=payload)

    def publish_to_dlq(
        self,
        raw_payload: bytes,
        error_reason: str,
        error_type: str,
        source_topic: str,
    ):
        """Publish an invalid message to the DLQ with metadata."""
        metadata = _extract_dlq_metadata(raw_payload, source_topic)
        envelope = {
            "original_payload": raw_payload.decode("utf-8", errors="replace"),
            "busId": metadata["busId"],
            "tripId": metadata["tripId"],
            "event_timestamp": metadata["event_timestamp"],
            "error_reason": error_reason,
            "error_type": error_type,
            "source": "mqtt",
            "source_topic": source_topic,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }

        self.producer.send(topic=self.dlq_topic, key=None, value=envelope)

    def close(self):
        self.producer.flush()
        self.producer.close()
