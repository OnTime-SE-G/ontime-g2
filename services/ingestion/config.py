# services/ingestion/config.py
# Ingestion Service configuration — loaded from environment variables.
# Uses pydantic-settings for type-safe config with .env support.

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionSettings(BaseSettings):
    """Configuration for the Ingestion Service."""

    # MQTT Broker (input source)
    mqtt_broker_host: str = Field(
        default="mqtt-broker",
        validation_alias="MQTT_BROKER_HOST",
        description="Hostname of the Mosquitto MQTT broker",
    )
    mqtt_broker_port: int = Field(
        default=1883,
        validation_alias="MQTT_BROKER_PORT",
        description="Port of the MQTT broker",
    )
    mqtt_topic_pattern: str = Field(
        default="transport/bus/+/location",
        validation_alias="MQTT_TOPIC_PATTERN",
        description="MQTT topic pattern to subscribe to (+ is single-level wildcard)",
    )

    # Kafka / AutoMQ (output destination)
    kafka_broker_url: str = Field(
        default="broker:29092",
        validation_alias="KAFKA_BROKER_URL",
        description="Bootstrap server for Kafka / AutoMQ",
    )
    kafka_raw_topic: str = Field(
        default="transport-telemetry-raw",
        validation_alias="KAFKA_RAW_TOPIC",
        description="Kafka topic for validated GPS messages",
    )
    kafka_dlq_topic: str = Field(
        default="transport-telemetry-dlq",
        validation_alias="KAFKA_DLQ_TOPIC",
        description="Kafka topic for invalid/rejected messages (Dead Letter Queue)",
    )

    # Health endpoint
    service_port: int = Field(
        default=8001,
        validation_alias="SERVICE_PORT",
        description="Port for the FastAPI health/metrics endpoint",
    )

    model_config = SettingsConfigDict(
        env_file="docker/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = IngestionSettings()
