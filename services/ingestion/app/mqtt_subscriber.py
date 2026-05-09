import logging
import json
from collections import deque
import paho.mqtt.client as mqtt

from schemas.gps import GPSLocationMessage, GPSMessage
from services.ingestion.app.config import settings
from services.ingestion.app.metrics import metrics
from services.ingestion.app.producer import TelemetryProducer
from services.ingestion.app.trip_lifecycle_cache import ActiveTripCache, ActiveTripInfo
from services.ingestion.app.validator import (
    StatefulValidator,
    ValidationResult,
    validate_gps_location_payload,
    validate_heartbeat_payload,
)

logger = logging.getLogger(__name__)


class MQTTSubscriber:
    def __init__(self, producer: TelemetryProducer, trip_cache: ActiveTripCache | None = None):
        if producer is None:
            raise ValueError("TelemetryProducer is required for MQTTSubscriber")

        self.producer = producer
        self.trip_cache = trip_cache
        self.validator = StatefulValidator()
        self.startup_buffer = deque(maxlen=settings.startup_buffer_max_messages)
        self.messages_received = 0
        self.messages_validated = 0
        self.messages_rejected = 0
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.mqtt_client_id,
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
        if settings.mqtt_username or settings.mqtt_password:
            self.client.username_pw_set(
                settings.mqtt_username,
                settings.mqtt_password,
            )
        if settings.mqtt_tls_enabled:
            if settings.mqtt_ca_cert_path:
                self.client.tls_set(ca_certs=settings.mqtt_ca_cert_path)
            else:
                self.client.tls_set()
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
            client.subscribe(
                [
                    (settings.mqtt_topic_pattern, 0),
                    (settings.mqtt_heartbeat_topic_pattern, 0),
                ]
            )
            logger.info(
                "Subscribed to topic patterns: %s, %s",
                settings.mqtt_topic_pattern,
                settings.mqtt_heartbeat_topic_pattern,
            )
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

        if self.trip_cache is not None and self.trip_cache.is_ready:
            self.drain_startup_buffer()

        if self._is_heartbeat_topic(msg.topic):
            self._process_heartbeat(msg.payload, msg.topic)
            return

        self._process_payload(msg.payload, msg.topic)

    def _is_heartbeat_topic(self, topic: str) -> bool:
        return topic.endswith("/heartbeat")

    def _process_payload(self, raw_payload: bytes, source_topic: str):
        location_result = validate_gps_location_payload(raw_payload)
        if not location_result.success or not location_result.location:
            self._reject(raw_payload, source_topic, location_result)
            return

        if self.trip_cache is not None and self.trip_cache.is_rebuilding:
            self._buffer_until_trip_cache_ready(raw_payload, source_topic)
            return

        enriched_message = self._enrich_location(location_result.location)
        if enriched_message is None:
            self._reject(
                raw_payload,
                source_topic,
                ValidationResult(
                    success=False,
                    error_reason=(
                        f"No active trip found for bus {location_result.location.bus_id}"
                    ),
                    error_type="INACTIVE_TRIP",
                ),
            )
            return

        stateful_result = self.validator.validate(self._serialize_message(enriched_message))
        if stateful_result.success and stateful_result.message:
            self.messages_validated += 1
            metrics.increment_validated()
            self.producer.publish_valid(stateful_result.message)
        else:
            self._reject(raw_payload, source_topic, stateful_result)

    def _process_heartbeat(self, raw_payload: bytes, source_topic: str):
        result = validate_heartbeat_payload(raw_payload)
        if result.success and result.heartbeat:
            metrics.record_heartbeat(
                bus_id=result.heartbeat.bus_id,
                timestamp=result.heartbeat.timestamp,
            )
            logger.debug("Recorded heartbeat from %s", result.heartbeat.bus_id)
            return

        metrics.increment_invalid_heartbeat()
        logger.warning(
            "Ignoring invalid heartbeat from %s: %s",
            source_topic,
            result.error_reason or "Unknown Error",
        )

    def drain_startup_buffer(self):
        while self.trip_cache is not None and self.trip_cache.is_ready and self.startup_buffer:
            raw_payload, source_topic = self.startup_buffer.popleft()
            self._process_payload(raw_payload, source_topic)

    def _buffer_until_trip_cache_ready(self, raw_payload: bytes, source_topic: str):
        if len(self.startup_buffer) == self.startup_buffer.maxlen:
            self._reject(
                raw_payload,
                source_topic,
                ValidationResult(
                    success=False,
                    error_reason="Trip cache is rebuilding and startup buffer is full",
                    error_type="TRIP_CACHE_REBUILDING",
                ),
            )
            return

        self.startup_buffer.append((raw_payload, source_topic))

    def _enrich_location(self, location: GPSLocationMessage) -> GPSMessage | None:
        active_trip: ActiveTripInfo | None = None
        if settings.require_active_trip and self.trip_cache is not None:
            active_trip = self.trip_cache.get_active_trip(location.bus_id)
            if active_trip is None:
                return None

        return GPSMessage(
            bus_id=location.bus_id,
            trip_id=active_trip.trip_id if active_trip else "UNSCOPED_TRIP",
            lat=location.lat,
            lon=location.lon,
            speed=location.speed,
            heading=location.heading,
            timestamp=location.timestamp,
        )

    def _serialize_message(self, message: GPSMessage) -> bytes:
        payload = message.model_dump(by_alias=True, mode="json")
        return json.dumps(payload).encode("utf-8")

    def _reject(self, raw_payload: bytes, source_topic: str, result: ValidationResult):
        self.messages_rejected += 1
        metrics.increment_rejected(result.error_type or "UNKNOWN")
        self.producer.publish_to_dlq(
            raw_payload=raw_payload,
            error_reason=result.error_reason or "Unknown Error",
            error_type=result.error_type or "UNKNOWN",
            source_topic=source_topic,
        )
