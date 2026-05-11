"""ETA Service configuration — all thresholds as environment variables.

All constants are overridable via env vars so no redeployment is needed
to tune thresholds (as required by JPabasara review, PR #101).
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    _REPO_ROOT = Path(__file__).resolve().parents[4]
    _ENV_FILES = (
        str(_REPO_ROOT / "docker" / ".env"),
        str(_REPO_ROOT / "docker" / ".env.example"),
    )
except (IndexError, ValueError):
    _ENV_FILES = ()


class EtaSettings(BaseSettings):
    """Runtime configuration for the ETA Service."""

    # ------------------------------------------------------------------ #
    # Database                                                             #
    # ------------------------------------------------------------------ #
    eta_database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/eta_db",
        validation_alias=AliasChoices("ETA_DATABASE_URL"),
        description="SQLAlchemy connection string for eta_db (PostgreSQL)",
    )

    # ------------------------------------------------------------------ #
    # Kafka                                                                #
    # ------------------------------------------------------------------ #
    kafka_broker_url: str = Field(
        default="broker:29092",
        validation_alias=AliasChoices("ETA_KAFKA_BROKER_URL", "KAFKA_BROKER_URL"),
        description="Kafka bootstrap server address",
    )
    kafka_topic: str = Field(
        default="transport-eta-features",
        validation_alias=AliasChoices("ETA_KAFKA_TOPIC"),
        description="Kafka topic consumed by ETA Service (Flink ETA features stream)",
    )
    kafka_consumer_group: str = Field(
        default="eta-service-group",
        validation_alias=AliasChoices("ETA_KAFKA_CONSUMER_GROUP"),
        description="Kafka consumer group ID",
    )

    # ------------------------------------------------------------------ #
    # Redis                                                                #
    # ------------------------------------------------------------------ #
    redis_host: str = Field(
        default="redis",
        validation_alias=AliasChoices("ETA_REDIS_HOST", "REDIS_HOST"),
        description="Redis host for ETA snapshots and Pub/Sub",
    )
    redis_port: int = Field(
        default=6379,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("ETA_REDIS_PORT", "REDIS_PORT"),
        description="Redis port",
    )

    # ------------------------------------------------------------------ #
    # HTTP                                                                 #
    # ------------------------------------------------------------------ #
    service_port: int = Field(
        default=8005,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("ETA_SERVICE_PORT"),
        description="Port the ETA Service FastAPI app listens on",
    )

    # ------------------------------------------------------------------ #
    # SARIMA model                                                         #
    # ------------------------------------------------------------------ #
    sarima_min_hours: int = Field(
        default=48,
        ge=1,
        validation_alias=AliasChoices("ETA_SARIMA_MIN_HOURS"),
        description=(
            "Minimum hours of hourly ETA history required before a SARIMA model "
            "is trained for a (route_id, stop_id) pair. "
            "48 h = 2 full S=24 seasonal cycles (JPabasara amendment)."
        ),
    )
    sarima_artifact_dir: str = Field(
        default="sarima_artifacts",
        validation_alias=AliasChoices("ETA_SARIMA_ARTIFACT_DIR"),
        description="Directory where train_sarima.py writes .joblib artifacts",
    )

    # ------------------------------------------------------------------ #
    # ETA records retention                                                #
    # ------------------------------------------------------------------ #
    eta_records_retention_months: int = Field(
        default=6,
        ge=1,
        validation_alias=AliasChoices("ETA_RECORDS_RETENTION_MONTHS"),
        description=(
            "Monthly table partitions older than this value are eligible to be "
            "dropped by the maintenance script. Uses PostgreSQL partition pruning "
            "(O(1) metadata drop) instead of a full-table DELETE scan."
        ),
    )

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = EtaSettings()
