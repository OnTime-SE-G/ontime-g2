from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_ROOT = Path(__file__).resolve().parent
DEFAULT_ISOLATION_FOREST_ARTIFACT_PATH = (
    SERVICE_ROOT / "models" / "training" / "isolation_forest.joblib"
)

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
    anomaly_database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/anomaly_db",
        validation_alias=AliasChoices("ANOMALY_DATABASE_URL"),
        description="SQLAlchemy connection string for anomaly_db",
    )
    redis_host: str = Field(
        default="redis",
        validation_alias=AliasChoices("ANOMALY_REDIS_HOST", "REDIS_HOST"),
        description="Redis host for anomaly live Pub/Sub",
    )
    redis_port: int = Field(
        default=6379,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("ANOMALY_REDIS_PORT", "REDIS_PORT"),
        description="Redis port for anomaly live Pub/Sub",
    )
    redis_anomaly_live_channel: str = Field(
        default="anomaly:live",
        validation_alias=AliasChoices("ANOMALY_REDIS_LIVE_CHANNEL", "ANOMALY_LIVE_CHANNEL"),
        description="Redis Pub/Sub channel for generic anomaly alerts (deprecated/fallback)",
    )
    redis_anomaly_passenger_channel: str = Field(
        default="anomaly:passenger",
        validation_alias=AliasChoices("ANOMALY_REDIS_PASSENGER_CHANNEL"),
        description="Redis Pub/Sub channel for passenger-facing anomaly alerts",
    )
    redis_anomaly_driver_channel: str = Field(
        default="anomaly:driver",
        validation_alias=AliasChoices("ANOMALY_REDIS_DRIVER_CHANNEL"),
        description="Redis Pub/Sub channel for driver-facing anomaly alerts",
    )
    redis_anomaly_admin_channel: str = Field(
        default="anomaly:admin",
        validation_alias=AliasChoices("ANOMALY_REDIS_ADMIN_CHANNEL"),
        description="Redis Pub/Sub channel for admin-facing anomaly alerts",
    )

    # Audience Targeting Routing Rules
    anomaly_passenger_types: str = Field(
        default="STATIONARY",
        validation_alias=AliasChoices("ANOMALY_PASSENGER_TYPES"),
        description="Comma-separated anomaly types broadcasted to passengers",
    )
    anomaly_driver_types: str = Field(
        default="OFF_ROUTE,PERSISTENT_OFF_ROUTE,UNREALISTIC_SPEED,STATIONARY",
        validation_alias=AliasChoices("ANOMALY_DRIVER_TYPES"),
        description="Comma-separated anomaly types broadcasted to drivers",
    )
    anomaly_admin_types: str = Field(
        default="ERRATIC_DRIVING,INACTIVE_GPS,TRIP_NOT_STARTED_DEVICE_ACTIVE,COMMUNICATION_LOSS,OFF_ROUTE,PERSISTENT_OFF_ROUTE,UNREALISTIC_SPEED,STATIONARY",
        validation_alias=AliasChoices("ANOMALY_ADMIN_TYPES"),
        description="Comma-separated anomaly types broadcasted to admins",
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
    off_route_distance_threshold_m: float = Field(
        default=50.0,
        ge=0.0,
        validation_alias=AliasChoices(
            "ANOMALY_OFF_ROUTE_DISTANCE_THRESHOLD_M",
            "OFF_ROUTE_DISTANCE_THRESHOLD_M",
        ),
        description="Distance from route polyline before a bus is considered off-route",
    )
    off_route_streak_window_seconds: int = Field(
        default=5,
        ge=1,
        validation_alias=AliasChoices(
            "ANOMALY_OFF_ROUTE_STREAK_WINDOW_SECONDS",
            "OFF_ROUTE_STREAK_WINDOW_SECONDS",
        ),
        description="Time window for consecutive off-route readings",
    )
    persistent_off_route_threshold: int = Field(
        default=3,
        ge=1,
        validation_alias=AliasChoices(
            "ANOMALY_PERSISTENT_OFF_ROUTE_THRESHOLD",
            "PERSISTENT_OFF_ROUTE_THRESHOLD",
        ),
        description="Readings in the streak window before PERSISTENT_OFF_ROUTE is emitted",
    )
    sliding_window_size: int = Field(
        default=20,
        ge=2,
        validation_alias=AliasChoices(
            "ANOMALY_SLIDING_WINDOW_SIZE",
            "SLIDING_WINDOW_SIZE",
        ),
        description="Number of recent telemetry pings used for Isolation Forest features",
    )
    sliding_window_min_size: int = Field(
        default=10,
        ge=2,
        validation_alias=AliasChoices(
            "ANOMALY_SLIDING_WINDOW_MIN_SIZE",
            "SLIDING_WINDOW_MIN_SIZE",
        ),
        description="Minimum telemetry pings required before Isolation Forest inference",
    )
    behavioral_fallback_speed_variance: float = Field(
        default=8.0,
        ge=0.0,
        validation_alias=AliasChoices("ANOMALY_BEHAVIORAL_FALLBACK_SPEED_VARIANCE"),
        description="Rule fallback: minimum speed variance for ERRATIC_DRIVING",
    )
    behavioral_fallback_heading_variance: float = Field(
        default=5.0,
        ge=0.0,
        validation_alias=AliasChoices("ANOMALY_BEHAVIORAL_FALLBACK_HEADING_VARIANCE"),
        description="Rule fallback: minimum heading variance for ERRATIC_DRIVING",
    )
    behavioral_fallback_max_acceleration: float = Field(
        default=3.0,
        ge=0.0,
        validation_alias=AliasChoices("ANOMALY_BEHAVIORAL_FALLBACK_MAX_ACCELERATION"),
        description="Rule fallback: max acceleration threshold (m/s^2) for ERRATIC_DRIVING",
    )
    isolation_forest_artifact_path: str = Field(
        default=str(DEFAULT_ISOLATION_FOREST_ARTIFACT_PATH),
        validation_alias=AliasChoices(
            "ANOMALY_ISOLATION_FOREST_ARTIFACT_PATH",
            "ISOLATION_FOREST_ARTIFACT_PATH",
        ),
        description="Path to the trained Isolation Forest .joblib artifact",
    )

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = AnomalySettings()
