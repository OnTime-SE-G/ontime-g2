from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILES = (
    str(REPO_ROOT / "docker" / ".env"),
    str(REPO_ROOT / "docker" / ".env.example"),
)


class AnomalySettings(BaseSettings):
    """Configuration for the anomaly service."""

    service_port: int = Field(
        default=8006,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("ANOMALY_SERVICE_PORT", "SERVICE_PORT"),
        description="HTTP port for anomaly health and metrics",
    )
    kafka_broker_url: str = Field(
        default="broker:29092",
        validation_alias=AliasChoices("ANOMALY_KAFKA_BROKER_URL", "KAFKA_BROKER_URL"),
        description="Kafka bootstrap server",
    )
    kafka_cleaned_topic: str = Field(
        default="transport-telemetry-cleaned",
        validation_alias=AliasChoices("ANOMALY_KAFKA_CLEANED_TOPIC", "KAFKA_CLEANED_TOPIC"),
        description="Cleaned/enriched GPS topic consumed by anomaly rules",
    )
    kafka_dlq_topic: str = Field(
        default="transport-telemetry-dlq",
        validation_alias=AliasChoices("ANOMALY_KAFKA_DLQ_TOPIC", "KAFKA_DLQ_TOPIC"),
        description="Ingestion DLQ topic consumed for rejection-based alerts",
    )
    kafka_anomaly_topic: str = Field(
        default="transport-anomaly-alerts",
        validation_alias=AliasChoices("ANOMALY_KAFKA_ALERTS_TOPIC", "KAFKA_ANOMALY_TOPIC"),
        description="Kafka topic for anomaly alerts",
    )
    kafka_cleaned_group_id: str = Field(
        default="anomaly-service-group",
        validation_alias=AliasChoices("ANOMALY_KAFKA_CLEANED_GROUP_ID", "KAFKA_CLEANED_GROUP_ID"),
        description="Kafka consumer group for cleaned telemetry",
    )
    kafka_dlq_group_id: str = Field(
        default="anomaly-service-dlq-group",
        validation_alias=AliasChoices("ANOMALY_KAFKA_DLQ_GROUP_ID", "KAFKA_DLQ_GROUP_ID"),
        description="Kafka consumer group for DLQ alerts",
    )
    route_service_url: str = Field(
        default="http://route-service:8002",
        validation_alias=AliasChoices("ANOMALY_ROUTE_SERVICE_URL", "ROUTE_SERVICE_URL"),
        description="Private Route Service base URL for route geometry",
    )
    route_fetch_timeout_seconds: float = Field(
        default=10.0,
        ge=0.1,
        validation_alias=AliasChoices("ANOMALY_ROUTE_FETCH_TIMEOUT_SECONDS", "ROUTE_FETCH_TIMEOUT_SECONDS"),
        description="HTTP timeout for route geometry fetches",
    )
    route_refresh_interval_seconds: int = Field(
        default=300,
        ge=1,
        validation_alias=AliasChoices("ANOMALY_ROUTE_REFRESH_INTERVAL_SECONDS", "ROUTE_REFRESH_INTERVAL_SECONDS"),
        description="How often anomaly refreshes route geometries",
    )
    communication_loss_check_interval_seconds: int = Field(
        default=60,
        ge=1,
        validation_alias=AliasChoices(
            "ANOMALY_COMMUNICATION_LOSS_CHECK_INTERVAL_SECONDS",
            "COMMUNICATION_LOSS_CHECK_INTERVAL_SECONDS",
        ),
        description="How often communication-loss rules run",
    )
    communication_loss_threshold_seconds: int = Field(
        default=180,
        ge=1,
        validation_alias=AliasChoices(
            "ANOMALY_COMMUNICATION_LOSS_THRESHOLD_SECONDS",
            "COMMUNICATION_LOSS_THRESHOLD_SECONDS",
        ),
        description="GPS silence threshold before communication-loss alerting",
    )
    inactive_trip_dlq_threshold_count: int = Field(
        default=3,
        ge=1,
        validation_alias=AliasChoices(
            "ANOMALY_INACTIVE_TRIP_DLQ_THRESHOLD_COUNT",
            "INACTIVE_TRIP_DLQ_THRESHOLD_COUNT",
        ),
        description="DLQ inactive-trip event count before alerting",
    )
    inactive_trip_dlq_window_seconds: int = Field(
        default=60,
        ge=1,
        validation_alias=AliasChoices(
            "ANOMALY_INACTIVE_TRIP_DLQ_WINDOW_SECONDS",
            "INACTIVE_TRIP_DLQ_WINDOW_SECONDS",
        ),
        description="Time window for inactive-trip DLQ aggregation",
    )
    inactive_trip_dlq_cooldown_seconds: int = Field(
        default=300,
        ge=1,
        validation_alias=AliasChoices(
            "ANOMALY_INACTIVE_TRIP_DLQ_COOLDOWN_SECONDS",
            "INACTIVE_TRIP_DLQ_COOLDOWN_SECONDS",
        ),
        description="Cooldown after emitting inactive-trip DLQ alert",
    )

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = AnomalySettings()
