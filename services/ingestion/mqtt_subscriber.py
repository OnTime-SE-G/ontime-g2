import logging
import paho.mqtt.client as mqtt

from services.ingestion.config import settings
from services.ingestion.producer import TelemetryProducer
from services.ingestion.validator import StatefulValidator

logger = logging.getLogger(__name__)


class MQTTSubscriber:
    def __init__(self, producer: TelemetryProducer):
        self.producer = producer
        self.validator = StatefulValidator()
        # Use Protocol v5 or v3.1.1 based on what paho-mqtt defaults to.
        # We specify a clean session for stateless consumption, relying on Kafka for persistence.
        self.client = mqtt.Client(clean_session=True)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

        # Basic counters for metrics (stub for Phase 6)
        self.messages_received = 0
        self.messages_validated = 0
        self.messages_rejected = 0

    def connect(self):
        logger.info(f"Connecting to MQTT broker at {settings.mqtt_broker_host}:{settings.mqtt_broker_port}")
        self.client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port, 60)

    def start(self):
        """Starts the blocking MQTT network loop."""
        logger.info("Starting MQTT subscriber loop...")
        self.client.loop_forever()

    def stop(self):
        """Stops the loop and disconnects."""
        logger.info("Stopping MQTT subscriber...")
        self.client.loop_stop()
        self.client.disconnect()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT broker successfully.")
            # Subscribe on connect so it resubscribes upon reconnection
            client.subscribe(settings.mqtt_topic_pattern)
            logger.info(f"Subscribed to topic pattern: {settings.mqtt_topic_pattern}")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker (code {rc}). Reconnecting...")
        else:
            logger.info("Disconnected from MQTT broker cleanly.")

    def on_message(self, client, userdata, msg):
        self.messages_received += 1
        
        result = self.validator.validate(msg.payload)

        if result.success and result.message:
            self.messages_validated += 1
            self.producer.publish_valid(result.message)
        else:
            self.messages_rejected += 1
            self.producer.publish_to_dlq(
                raw_payload=msg.payload,
                error_reason=result.error_reason or "Unknown Error",
                error_type=result.error_type or "UNKNOWN",
                source_topic=msg.topic
            )
