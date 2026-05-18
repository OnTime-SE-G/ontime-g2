"""ETA Service configuration — all thresholds as environment variables.

All constants are overridable via env vars so no redeployment is needed
to tune thresholds (as required by JPabasara review, PR #101).
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_ROOT = Path(__file__).resolve().parents[1]

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
    default_model: str = Field(
        default="xgboost",
        validation_alias=AliasChoices("ETA_DEFAULT_MODEL"),
        description="Default realtime ETA model: sarima, xgboost, or physics",
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
    eta_live_channel: str = Field(
        default="eta:live",
        validation_alias=AliasChoices("ETA_LIVE_CHANNEL"),
        description="Redis Pub/Sub channel for live ETA events",
    )
    eta_snapshot_ttl_seconds: int = Field(
        default=300,
        ge=1,
        validation_alias=AliasChoices("ETA_SNAPSHOT_TTL_SECONDS"),
        description="TTL for Redis trip ETA snapshots",
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
        default=str(_SERVICE_ROOT / "sarima_artifacts"),
        validation_alias=AliasChoices("ETA_SARIMA_ARTIFACT_DIR"),
        description="Directory where train_sarima.py writes .joblib artifacts",
    )
    xgb_artifact_path: str = Field(
        default=str(_SERVICE_ROOT / "models" / "training" / "eta_model_xgb.joblib"),
        validation_alias=AliasChoices("ETA_XGB_ARTIFACT_PATH"),
        description="Path to the trained XGBoost ETA .joblib artifact",
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

    # ------------------------------------------------------------------ #
    # MLflow and Fallbacks                                                 #
    # ------------------------------------------------------------------ #
    mlflow_tracking_uri: str = Field(default="http://mlflow:5000", validation_alias=AliasChoices("ETA_MLFLOW_TRACKING_URI"))
    mlflow_model_eta: str = Field(default="ontime-eta-xgb", validation_alias=AliasChoices("ETA_MLFLOW_MODEL_ETA"))
    mlflow_model_eta_urban: str = Field(default="ontime-eta-xgb-urban", validation_alias=AliasChoices("ETA_MLFLOW_MODEL_ETA_URBAN"))
    mlflow_model_eta_expressway: str = Field(default="ontime-eta-xgb-expressway", validation_alias=AliasChoices("ETA_MLFLOW_MODEL_ETA_EXPRESSWAY"))
    mlflow_model_sarima: str = Field(default="ontime-eta-sarima", validation_alias=AliasChoices("ETA_MLFLOW_MODEL_SARIMA"))
    model_stage: str = Field(default="Production", validation_alias=AliasChoices("ETA_MODEL_STAGE"))
    model_artifact_fallback_path: str = Field(default="", validation_alias=AliasChoices("ETA_MODEL_ARTIFACT_FALLBACK_PATH"))

    # ------------------------------------------------------------------ #
    # Smoothing / Fortification                                            #
    # ------------------------------------------------------------------ #
    eta_smoothing_window_size: int = Field(
        default=10,
        validation_alias=AliasChoices("ETA_SMOOTHING_WINDOW_SIZE"),
        description="Size of the moving average window for ETA smoothing"
    )
    eta_smoothing_ttl_seconds: int = Field(
        default=120,
        validation_alias=AliasChoices("ETA_SMOOTHING_TTL_SECONDS"),
        description="TTL for events in the moving average window"
    )

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = EtaSettings()
