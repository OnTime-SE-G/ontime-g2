from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILES = (
    str(REPO_ROOT / "docker" / ".env"),
    str(REPO_ROOT / "docker" / ".env.example"),
)


class IngestionSettings(BaseSettings):
    """Configuration for the ingestion service."""

    mqtt_broker_host: str = Field(
        default="mqtt-broker",
        validation_alias=AliasChoices("INGESTION_MQTT_BROKER_HOST", "MQTT_BROKER_HOST"),
        description="Hostname of the Mosquitto MQTT broker",
    )
    mqtt_broker_port: int = Field(
        default=1883,
        validation_alias=AliasChoices("INGESTION_MQTT_BROKER_PORT", "MQTT_BROKER_PORT"),
        description="Port of the MQTT broker",
    )
    mqtt_topic_pattern: str = Field(
        default="transport/bus/+/location",
        validation_alias=AliasChoices("INGESTION_MQTT_TOPIC_PATTERN", "MQTT_TOPIC_PATTERN"),
        description="MQTT topic pattern to subscribe to",
    )

    kafka_broker_url: str = Field(
        default="broker:29092",
        validation_alias=AliasChoices("INGESTION_KAFKA_BROKER_URL", "KAFKA_BROKER_URL"),
        description="Bootstrap server for Kafka or AutoMQ",
    )
    kafka_raw_topic: str = Field(
        default="transport-telemetry-raw",
        validation_alias=AliasChoices("INGESTION_KAFKA_RAW_TOPIC", "KAFKA_RAW_TOPIC"),
        description="Kafka topic for validated GPS messages",
    )
    kafka_dlq_topic: str = Field(
        default="transport-telemetry-dlq",
        validation_alias=AliasChoices("INGESTION_KAFKA_DLQ_TOPIC", "KAFKA_DLQ_TOPIC"),
        description="Kafka topic for rejected messages",
    )

    service_port: int = Field(
        default=8001,
        validation_alias=AliasChoices("INGESTION_SERVICE_PORT", "SERVICE_PORT"),
        description="Port for the FastAPI health and metrics server",
    )
    min_message_interval_seconds: float = Field(
        default=1.0,
        ge=0,
        validation_alias=AliasChoices(
            "INGESTION_MIN_MESSAGE_INTERVAL_SECONDS",
            "MIN_MESSAGE_INTERVAL_SECONDS",
        ),
        description="Minimum accepted interval between messages from the same bus",
    )
    duplicate_cache_size: int = Field(
        default=100,
        ge=1,
        validation_alias=AliasChoices(
            "INGESTION_DUPLICATE_CACHE_SIZE",
            "DUPLICATE_CACHE_SIZE",
        ),
        description="Number of recent payload hashes kept per bus for duplicate detection",
    )

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = IngestionSettings()
