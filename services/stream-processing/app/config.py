from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    ENV_FILES = (
        str(REPO_ROOT / "docker" / ".env"),
        str(REPO_ROOT / "docker" / ".env.example"),
    )
except (IndexError, ValueError):
    # Fallback for Docker or unusual structures
    REPO_ROOT = Path(__file__).resolve().parents[1]
    ENV_FILES = ()


class StreamSettings(BaseSettings):
    """Configuration for the PyFlink stream-processing job."""

    kafka_broker_url: str = Field(
        default="broker:29092",
        validation_alias=AliasChoices("STREAM_KAFKA_BROKER_URL", "KAFKA_BROKER_URL"),
        description="Kafka bootstrap server",
    )
    kafka_raw_topic: str = Field(
        default="transport-telemetry-raw",
        validation_alias=AliasChoices("STREAM_KAFKA_RAW_TOPIC", "KAFKA_RAW_TOPIC"),
        description="Raw active-trip GPS topic",
    )
    kafka_cleaned_topic: str = Field(
        default="transport-telemetry-cleaned",
        validation_alias=AliasChoices("STREAM_KAFKA_CLEANED_TOPIC", "KAFKA_CLEANED_TOPIC"),
        description="Cleaned/enriched GPS topic",
    )
    kafka_eta_features_topic: str = Field(
        default="transport-eta-features",
        validation_alias=AliasChoices("STREAM_KAFKA_ETA_FEATURES_TOPIC", "KAFKA_ETA_FEATURES_TOPIC"),
        description="ETA-enriched GPS topic used by ETA service consumer",
    )
    kafka_lifecycle_topic: str = Field(
        default="trip.lifecycle",
        validation_alias=AliasChoices("STREAM_KAFKA_LIFECYCLE_TOPIC", "KAFKA_LIFECYCLE_TOPIC"),
        description="Trip lifecycle topic used for route/trip state",
    )
    kafka_consumer_group: str = Field(
        default="stream-processing-group",
        validation_alias=AliasChoices("STREAM_KAFKA_CONSUMER_GROUP", "KAFKA_CONSUMER_GROUP"),
        description="Kafka consumer group for raw telemetry",
    )
    kafka_lifecycle_consumer_group: str = Field(
        default="stream-processing-lifecycle-group",
        validation_alias=AliasChoices(
            "STREAM_KAFKA_LIFECYCLE_CONSUMER_GROUP",
            "KAFKA_LIFECYCLE_CONSUMER_GROUP",
        ),
        description="Kafka consumer group for lifecycle events",
    )

    redis_host: str = Field(
        default="redis",
        validation_alias=AliasChoices("STREAM_REDIS_HOST", "REDIS_HOST"),
        description="Redis host for live position snapshots and Pub/Sub",
    )
    redis_port: int = Field(
        default=6379,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("STREAM_REDIS_PORT", "REDIS_PORT"),
        description="Redis port",
    )
    redis_fleet_live_channel: str = Field(
        default="fleet:live",
        validation_alias=AliasChoices("STREAM_REDIS_FLEET_LIVE_CHANNEL", "FLEET_CHANNEL"),
        description="Redis Pub/Sub channel for live fleet updates",
    )

    influxdb_url: str = Field(
        default="http://influxdb:8086",
        validation_alias=AliasChoices("STREAM_INFLUXDB_URL", "INFLUXDB_URL"),
        description="InfluxDB URL for telemetry history",
    )
    influxdb_token: str = Field(
        default="super_secret_admin_token_123",
        validation_alias=AliasChoices(
            "STREAM_INFLUXDB_TOKEN",
            "INFLUXDB_TOKEN",
            "INFLUXDB_ADMIN_TOKEN",
        ),
        description="InfluxDB token",
    )
    influxdb_org: str = Field(
        default="ontime",
        validation_alias=AliasChoices("STREAM_INFLUXDB_ORG", "INFLUXDB_ORG", "INFLUXDB_INIT_ORG"),
        description="InfluxDB organization",
    )
    influxdb_bucket: str = Field(
        default="telemetry",
        validation_alias=AliasChoices(
            "STREAM_INFLUXDB_BUCKET",
            "INFLUXDB_BUCKET",
            "INFLUXDB_INIT_BUCKET",
        ),
        description="InfluxDB bucket for GPS telemetry",
    )

    route_service_url: str = Field(
        default="http://route-service:8002",
        validation_alias=AliasChoices("STREAM_ROUTE_SERVICE_URL", "ROUTE_SERVICE_URL"),
        description="Private Route Service base URL",
    )
    flink_parallelism: int = Field(
        default=1,
        ge=1,
        validation_alias=AliasChoices("STREAM_FLINK_PARALLELISM", "FLINK_PARALLELISM"),
        description="Flink job parallelism",
    )

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = StreamSettings()
