import json
import logging
import asyncio
from aiokafka import AIOKafkaConsumer
from sqlalchemy.orm import Session
from app.config import settings
from app.database import SessionLocal
from app.models.db_fleet import DriverORM

logger = logging.getLogger(__name__)

class KafkaConsumerService:
    def __init__(self):
        self.consumer = None
        self.task = None

    async def start(self):
        try:
            self.consumer = AIOKafkaConsumer(
                "user-events",
                bootstrap_servers=settings.kafka_broker_url,
                group_id="fleet-management-group",
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            await self.consumer.start()
            logger.info("Kafka Consumer started.")
            self.task = asyncio.create_task(self.consume_messages())
        except Exception as e:
            logger.error(f"Failed to start Kafka Consumer: {e}")

    async def stop(self):
        if self.task:
            self.task.cancel()
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka Consumer stopped.")

    async def consume_messages(self):
        try:
            async for msg in self.consumer:
                try:
                    payload = msg.value
                    event = payload.get("event")
                    data = payload.get("data", {})
                    
                    if event == "USER_CREATED" and data.get("role") == "DRIVER":
                        self.handle_driver_created(data)
                        
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        except asyncio.CancelledError:
            pass

    def handle_driver_created(self, data: dict):
        db: Session = SessionLocal()
        try:
            driver_id = data.get("id")
            name = data.get("name")
            
            if not driver_id or not name:
                logger.warning("Invalid driver data received")
                return

            # Check if exists
            existing = db.query(DriverORM).filter(DriverORM.id == driver_id).first()
            if existing:
                existing.name = name
            else:
                new_driver = DriverORM(id=driver_id, name=name)
                db.add(new_driver)
            
            db.commit()
            logger.info(f"Driver {driver_id} updated in shadow cache.")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save driver to shadow cache: {e}")
        finally:
            db.close()

kafka_consumer_service = KafkaConsumerService()
