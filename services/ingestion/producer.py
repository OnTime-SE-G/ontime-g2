import json
import logging
from datetime import datetime, timezone

from kafka import KafkaProducer

from schemas.gps import GPSMessage
from services.ingestion.config import settings

logger = logging.getLogger(__name__)


class TelemetryProducer:
    def __init__(self):
        self.producer = KafkaProducer(
            bootstrap_servers=settings.kafka_broker_url,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: str(k).encode("utf-8") if k else None,
            acks="all",
        )
        self.raw_topic = settings.kafka_raw_topic
        self.dlq_topic = settings.kafka_dlq_topic
        logger.info(f"Initialized Kafka producer for {settings.kafka_broker_url}")

    def publish_valid(self, message: GPSMessage):
        """Publish a valid GPS message to the raw telemetry topic."""
        # Use by_alias=True to serialize camelCase (e.g. busId, tripId)
        payload = message.model_dump(by_alias=True)
        # Convert timestamp to ISO format for JSON serialization
        if "timestamp" in payload and isinstance(payload["timestamp"], datetime):
            payload["timestamp"] = payload["timestamp"].isoformat()
            
        key = message.bus_id
        
        self.producer.send(
            topic=self.raw_topic,
            key=key,
            value=payload
        )

    def publish_to_dlq(self, raw_payload: bytes, error_reason: str, error_type: str, source_topic: str):
        """Publish an invalid message to the Dead Letter Queue with metadata."""
        envelope = {
            "original_payload": raw_payload.decode("utf-8", errors="replace"),
            "error_reason": error_reason,
            "error_type": error_type,
            "source": "mqtt",
            "source_topic": source_topic,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        
        self.producer.send(
            topic=self.dlq_topic,
            key=None,
            value=envelope
        )

    def close(self):
        """Flush and close the Kafka producer."""
        self.producer.flush()
        self.producer.close()
