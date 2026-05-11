import json
import logging
import threading
from typing import Callable

from kafka import KafkaConsumer

from services.ingestion.app.config import settings

logger = logging.getLogger(__name__)


class DeviceConfigConsumer:
    """Consumes config JSON from Kafka and translates to MQTT string."""

    def __init__(self, publish_config_callback: Callable[[str, str], None]):
        self.publish_config_callback = publish_config_callback
        self.consumer = None
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        logger.info("Starting DeviceConfigConsumer thread...")
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        logger.info("Stopping DeviceConfigConsumer...")
        self._stop_event.set()
        if self.consumer:
            self.consumer.close()
        if self._thread:
            self._thread.join()

    def _run(self):
        try:
            self.consumer = KafkaConsumer(
                settings.kafka_device_config_topic,
                bootstrap_servers=settings.kafka_broker_url,
                group_id=settings.device_config_consumer_group,
                auto_offset_reset="latest",
                value_deserializer=lambda x: json.loads(x.decode("utf-8")),
            )
            logger.info(
                "DeviceConfigConsumer subscribed to %s",
                settings.kafka_device_config_topic,
            )
        except Exception as e:
            logger.error("Failed to connect DeviceConfigConsumer to Kafka: %s", e)
            return

        while not self._stop_event.is_set():
            try:
                # poll for messages so we can check stop_event
                messages = self.consumer.poll(timeout_ms=1000)
                for topic_partition, records in messages.items():
                    for record in records:
                        self._process_message(record.value)
            except Exception as e:
                logger.error("Error in DeviceConfigConsumer poll loop: %s", e)

    def _process_message(self, payload: dict):
        try:
            bus_id = payload.get("bus_id")
            if not bus_id:
                logger.error("Invalid config payload: missing bus_id")
                return

            # Build Arduino-friendly string: I:10000,H:30000
            config_parts = []
            if "location_interval" in payload:
                config_parts.append(f"I:{payload['location_interval']}")
            if "heartbeat_interval" in payload:
                config_parts.append(f"H:{payload['heartbeat_interval']}")
            if "new_bus_id" in payload:
                config_parts.append(f"B:{payload['new_bus_id']}")

            if config_parts:
                config_str = ",".join(config_parts)
                # Call the MQTT publisher
                self.publish_config_callback(str(bus_id), config_str)
            else:
                logger.warning("Empty config payload for bus %s", bus_id)

        except Exception as e:
            logger.error("Failed to process config message: %s", e)
