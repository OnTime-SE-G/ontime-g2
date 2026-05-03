import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILES = (
    str(REPO_ROOT / "docker" / ".env"),
    str(REPO_ROOT / "docker" / ".env.example"),
)

class StreamSettings(BaseSettings):
    kafka_broker_url: str = "broker:29092"
    kafka_raw_topic: str = "transport-telemetry-raw"
    kafka_cleaned_topic: str = "transport-telemetry-cleaned"
    kafka_lifecycle_topic: str = "trip.lifecycle"

    redis_host: str = "redis"
    redis_port: int = 6379

    influxdb_url: str = "http://influxdb:8086"
    influxdb_token: str = "super_secret_admin_token_123"
    influxdb_org: str = "ontime"
    influxdb_bucket: str = "telemetry"

    route_service_url: str = "http://route-service:8002"

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

settings = StreamSettings()
