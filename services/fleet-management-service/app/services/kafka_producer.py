import json
import logging
from aiokafka import AIOKafkaProducer
from app.config import settings
from schemas.trip_lifecycle import TripLifecycleEvent

logger = logging.getLogger(__name__)


class KafkaProducerService:
    def __init__(self):
        self._producer: AIOKafkaProducer | None = None

    async def _get_producer(self) -> AIOKafkaProducer:
        """Lazily create and connect the producer on first use."""
        if self._producer is None:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_broker_url
            )
            await self._producer.start()
            logger.info("Kafka producer connected to %s", settings.kafka_broker_url)
        return self._producer

    async def stop(self):
        if self._producer:
            await self._producer.stop()
            self._producer = None
            logger.info("Kafka producer stopped")

    async def publish_trip_event(self, event: TripLifecycleEvent):
        producer = await self._get_producer()
        try:
            payload = event.model_dump(by_alias=True)
            await producer.send_and_wait(
                settings.kafka_trip_lifecycle_topic,
                json.dumps(payload, default=str).encode("utf-8")
            )
            logger.info("Published %s for trip %s", event.event, event.trip_id)
        except Exception:
            # Reset producer so next call re-connects
            self._producer = None
            logger.exception("Failed to publish trip lifecycle event")
            raise


kafka_service = KafkaProducerService()

