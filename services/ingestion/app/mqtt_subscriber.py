import logging

import paho.mqtt.client as mqtt

from services.ingestion.app.config import settings
from services.ingestion.app.metrics import metrics
from services.ingestion.app.producer import TelemetryProducer
from services.ingestion.app.validator import StatefulValidator

logger = logging.getLogger(__name__)


class MQTTSubscriber:
    def __init__(self, producer: TelemetryProducer):
        if producer is None:
            raise ValueError("TelemetryProducer is required for MQTTSubscriber")

        self.producer = producer
        self.validator = StatefulValidator()
        self.messages_received = 0
        self.messages_validated = 0
        self.messages_rejected = 0
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            clean_session=True,
        )
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

    def connect(self):
        logger.info(
            "Connecting to MQTT broker at %s:%s",
            settings.mqtt_broker_host,
            settings.mqtt_broker_port,
        )
        self.client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port, 60)

    def start(self):
        logger.info("Starting MQTT subscriber loop...")
        self.client.loop_forever()

    def stop(self):
        logger.info("Stopping MQTT subscriber...")
        self.client.loop_stop()
        self.client.disconnect()

    def on_connect(self, client, userdata, connect_flags, reason_code, properties):
        if reason_code == 0:
            logger.info("Connected to MQTT broker successfully.")
            client.subscribe(settings.mqtt_topic_pattern)
            logger.info("Subscribed to topic pattern: %s", settings.mqtt_topic_pattern)
            metrics.mqtt_broker_up = True
        else:
            logger.error("Failed to connect to MQTT broker, return code %s", reason_code)
            metrics.mqtt_broker_up = False

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        if reason_code != 0:
            logger.warning(
                "Unexpected disconnection from MQTT broker (code %s). Reconnecting...",
                reason_code,
            )
            metrics.mqtt_broker_up = False
        else:
            logger.info("Disconnected from MQTT broker cleanly.")
            metrics.mqtt_broker_up = False

    def on_message(self, client, userdata, msg):
        self.messages_received += 1
        metrics.increment_received()

        result = self.validator.validate(msg.payload)

        if result.success and result.message:
            self.messages_validated += 1
            metrics.increment_validated()
            self.producer.publish_valid(result.message)
        else:
            self.messages_rejected += 1
            metrics.increment_rejected(result.error_type or "UNKNOWN")
            self.producer.publish_to_dlq(
                raw_payload=msg.payload,
                error_reason=result.error_reason or "Unknown Error",
                error_type=result.error_type or "UNKNOWN",
                source_topic=msg.topic,
            )
