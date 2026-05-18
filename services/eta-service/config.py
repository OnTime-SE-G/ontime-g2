"""ETA service configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ETA_", extra="ignore")

    database_url: str = (
        "postgresql://postgres:postgres@postgres:5432/eta_db"
    )
    default_model: str = "xgboost"
    snapshot_ttl_seconds: int = 300
    kafka_broker_url: str = "broker:29092"
    kafka_topic: str = "transport-eta-features"
    kafka_group_id: str = "eta-service"
    service_port: int = 8005

    mlflow_tracking_uri: str = "http://mlflow:5000"
    mlflow_model_eta: str = "ontime-eta-xgb"
    mlflow_model_eta_urban: str = "ontime-eta-xgb-urban"
    mlflow_model_eta_expressway: str = "ontime-eta-xgb-expressway"
    mlflow_model_sarima: str = "ontime-eta-sarima"
    model_stage: str = "Production"
    model_artifact_fallback_path: str = ""

    sarima_min_threshold_hours: int = 48
    sarima_artifact_dir: str = "models/training/sarima_artifacts"


settings = Settings()
