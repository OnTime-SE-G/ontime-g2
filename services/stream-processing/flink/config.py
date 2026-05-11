from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILES = (
    str(REPO_ROOT / "docker" / ".env"),
    str(REPO_ROOT / "docker" / ".env.example"),
)


class FlinkConnectorSettings(BaseSettings):
    """Connector/runtime settings for the CR1 Flink pipeline scaffold."""

    kafka_broker_url: str = Field(
        default="broker:29092",
        validation_alias=AliasChoices("STREAM_KAFKA_BROKER_URL", "KAFKA_BROKER_URL"),
    )
    kafka_raw_topic: str = Field(
        default="transport-telemetry-raw",
        validation_alias=AliasChoices("STREAM_KAFKA_RAW_TOPIC", "KAFKA_RAW_TOPIC"),
    )
    kafka_cleaned_topic: str = Field(
        default="transport-telemetry-cleaned",
        validation_alias=AliasChoices("STREAM_KAFKA_CLEANED_TOPIC", "KAFKA_CLEANED_TOPIC"),
    )
    kafka_invalid_topic: str = Field(
        default="telemetry-invalid",
        validation_alias=AliasChoices("STREAM_KAFKA_INVALID_TOPIC", "KAFKA_INVALID_TOPIC"),
    )
    kafka_trip_lifecycle_topic: str = Field(
        default="trip.lifecycle",
        validation_alias=AliasChoices(
            "STREAM_KAFKA_TRIP_LIFECYCLE_TOPIC",
            "KAFKA_TRIP_LIFECYCLE_TOPIC",
        ),
    )
    kafka_raw_consumer_group: str = Field(
        default="stream-processing-raw-group",
        validation_alias=AliasChoices(
            "STREAM_KAFKA_RAW_CONSUMER_GROUP",
            "KAFKA_RAW_CONSUMER_GROUP",
        ),
    )
    kafka_lifecycle_consumer_group: str = Field(
        default="stream-processing-lifecycle-group",
        validation_alias=AliasChoices(
            "STREAM_KAFKA_LIFECYCLE_CONSUMER_GROUP",
            "KAFKA_LIFECYCLE_CONSUMER_GROUP",
        ),
    )

    route_service_cache_url: str = Field(
        default="http://route-service:8002/internal/routes/cache",
        validation_alias=AliasChoices(
            "STREAM_ROUTE_SERVICE_CACHE_URL",
            "ROUTE_SERVICE_CACHE_URL",
        ),
    )
    fleet_service_active_trips_url: str = Field(
        default="http://fleet-management-service:8003/internal/trips/active",
        validation_alias=AliasChoices(
            "STREAM_FLEET_SERVICE_ACTIVE_TRIPS_URL",
            "FLEET_SERVICE_ACTIVE_TRIPS_URL",
        ),
    )
    startup_cache_timeout_seconds: float = Field(
        default=5.0,
        ge=0.1,
        validation_alias=AliasChoices(
            "STREAM_STARTUP_CACHE_TIMEOUT_SECONDS",
            "STARTUP_CACHE_TIMEOUT_SECONDS",
        ),
    )

    redis_host: str = Field(
        default="redis",
        validation_alias=AliasChoices("STREAM_REDIS_HOST", "REDIS_HOST"),
    )
    redis_port: int = Field(
        default=6379,
        validation_alias=AliasChoices("STREAM_REDIS_PORT", "REDIS_PORT"),
    )
    redis_live_channel: str = Field(
        default="fleet:live",
        validation_alias=AliasChoices("STREAM_REDIS_LIVE_CHANNEL", "REDIS_LIVE_CHANNEL"),
    )

    influxdb_url: str = Field(
        default="http://influxdb:8086",
        validation_alias=AliasChoices("STREAM_INFLUXDB_URL", "INFLUXDB_URL"),
    )
    influxdb_token: str = Field(
        default="super_secret_admin_token_123",
        validation_alias=AliasChoices("STREAM_INFLUXDB_TOKEN", "INFLUXDB_TOKEN"),
    )
    influxdb_org: str = Field(
        default="ontime",
        validation_alias=AliasChoices("STREAM_INFLUXDB_ORG", "INFLUXDB_ORG"),
    )
    influxdb_bucket: str = Field(
        default="telemetry",
        validation_alias=AliasChoices("STREAM_INFLUXDB_BUCKET", "INFLUXDB_BUCKET"),
    )

    flink_parallelism: int = Field(
        default=1,
        ge=1,
        validation_alias=AliasChoices("STREAM_FLINK_PARALLELISM", "FLINK_PARALLELISM"),
    )

    route_deviation_threshold_meters: float = Field(
        default=50.0,
        ge=0.0,
        validation_alias=AliasChoices(
            "STREAM_ROUTE_DEVIATION_THRESHOLD_METERS",
            "ROUTE_DEVIATION_THRESHOLD_METERS",
        ),
        description="Maximum distance in meters from route polyline considered on-route",
    )

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = FlinkConnectorSettings()
