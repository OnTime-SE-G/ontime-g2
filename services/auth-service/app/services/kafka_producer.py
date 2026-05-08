import json
import logging
from aiokafka import AIOKafkaProducer
from app.config import settings

logger = logging.getLogger(__name__)

class KafkaService:
    def __init__(self):
        self.producer = None

    async def start(self):
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=settings.KAFKA_BROKER_URL,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            await self.producer.start()
            logger.info("Kafka Producer started.")
        except Exception as e:
            logger.error(f"Failed to start Kafka Producer: {e}")

    async def stop(self):
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka Producer stopped.")

    async def publish_event(self, topic: str, event_type: str, payload: dict):
        if not self.producer:
            logger.warning("Kafka Producer is not initialized. Event not published.")
            return

        message = {
            "event": event_type,
            "data": payload
        }
        try:
            await self.producer.send_and_wait(topic, value=message)
            logger.info(f"Published event {event_type} to topic {topic}")
        except Exception as e:
            logger.error(f"Failed to publish event to Kafka: {e}")

kafka_service = KafkaService()
