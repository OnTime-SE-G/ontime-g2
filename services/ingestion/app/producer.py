import json
import logging
from datetime import datetime, timezone

from kafka import KafkaProducer

from schemas.gps import GPSMessage
from services.ingestion.app.config import settings

logger = logging.getLogger(__name__)


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
        envelope = {
            "original_payload": raw_payload.decode("utf-8", errors="replace"),
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
