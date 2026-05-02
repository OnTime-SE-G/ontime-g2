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
    mqtt_heartbeat_topic_pattern: str = Field(
        default="transport/bus/+/heartbeat",
        validation_alias=AliasChoices(
            "INGESTION_MQTT_HEARTBEAT_TOPIC_PATTERN",
            "MQTT_HEARTBEAT_TOPIC_PATTERN",
        ),
        description="MQTT topic pattern for GPS device-status heartbeats",
    )
    mqtt_tls_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("INGESTION_MQTT_TLS_ENABLED", "MQTT_TLS_ENABLED"),
        description="Enable TLS for MQTT broker connections",
    )
    mqtt_username: str | None = Field(
        default=None,
        validation_alias=AliasChoices("INGESTION_MQTT_USERNAME", "MQTT_USERNAME"),
        description="Optional MQTT username",
    )
    mqtt_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("INGESTION_MQTT_PASSWORD", "MQTT_PASSWORD"),
        description="Optional MQTT password",
    )
    mqtt_client_id: str = Field(
        default="ontime-ingestion-service",
        validation_alias=AliasChoices("INGESTION_MQTT_CLIENT_ID", "MQTT_CLIENT_ID"),
        description="MQTT client identifier for ingestion",
    )
    mqtt_ca_cert_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("INGESTION_MQTT_CA_CERT_PATH", "MQTT_CA_CERT_PATH"),
        description="Optional CA certificate path for MQTT TLS",
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
    kafka_trip_lifecycle_topic: str = Field(
        default="trip.lifecycle",
        validation_alias=AliasChoices(
            "INGESTION_KAFKA_TRIP_LIFECYCLE_TOPIC",
            "KAFKA_TRIP_LIFECYCLE_TOPIC",
        ),
        description="Kafka topic for Fleet trip lifecycle events",
    )
    trip_cache_consumer_group: str = Field(
        default="ingestion-trip-cache",
        validation_alias=AliasChoices(
            "INGESTION_TRIP_CACHE_CONSUMER_GROUP",
            "TRIP_CACHE_CONSUMER_GROUP",
        ),
        description="Kafka consumer group for ingestion active trip cache",
    )
    require_active_trip: bool = Field(
        default=True,
        validation_alias=AliasChoices("INGESTION_REQUIRE_ACTIVE_TRIP", "REQUIRE_ACTIVE_TRIP"),
        description="Reject GPS unless bus has an active trip in the local cache",
    )
    trip_cache_rebuild_timeout_seconds: float = Field(
        default=60.0,
        ge=0,
        validation_alias=AliasChoices(
            "INGESTION_TRIP_CACHE_REBUILD_TIMEOUT_SECONDS",
            "TRIP_CACHE_REBUILD_TIMEOUT_SECONDS",
        ),
        description="Maximum time allowed for initial trip cache rebuild",
    )
    startup_buffer_max_messages: int = Field(
        default=1000,
        ge=1,
        validation_alias=AliasChoices(
            "INGESTION_STARTUP_BUFFER_MAX_MESSAGES",
            "STARTUP_BUFFER_MAX_MESSAGES",
        ),
        description="Maximum GPS messages buffered while trip cache is rebuilding",
    )

    service_port: int = Field(
        default=8001,
        validation_alias=AliasChoices("INGESTION_SERVICE_PORT", "SERVICE_PORT"),
        description="Port for the FastAPI health and metrics server",
    )
    min_message_interval_seconds: float = Field(
        default=3.0,
        ge=0,
        validation_alias=AliasChoices(
            "INGESTION_MIN_MESSAGE_INTERVAL_SECONDS",
            "MIN_MESSAGE_INTERVAL_SECONDS",
        ),
        description="Minimum accepted interval between messages from the same bus",
    )
    min_event_interval_seconds: float = Field(
        default=1.0,
        ge=0,
        validation_alias=AliasChoices(
            "INGESTION_MIN_EVENT_INTERVAL_SECONDS",
            "MIN_EVENT_INTERVAL_SECONDS",
        ),
        description="Minimum accepted event-time interval between messages from the same bus",
    )
    max_future_skew_seconds: float = Field(
        default=30.0,
        ge=0,
        validation_alias=AliasChoices(
            "INGESTION_MAX_FUTURE_SKEW_SECONDS",
            "MAX_FUTURE_SKEW_SECONDS",
        ),
        description="Maximum allowed future event-time skew in seconds",
    )
    max_stale_age_seconds: float = Field(
        default=86400.0,
        ge=0,
        validation_alias=AliasChoices(
            "INGESTION_MAX_STALE_AGE_SECONDS",
            "MAX_STALE_AGE_SECONDS",
        ),
        description="Maximum allowed event age before stale replay rejection",
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
