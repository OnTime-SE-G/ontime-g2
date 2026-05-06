from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILES = (
    str(REPO_ROOT / "docker" / ".env"),
    str(REPO_ROOT / "docker" / ".env.example"),
)


class ApiGatewaySettings(BaseSettings):
    """Configuration for the G2 API Gateway facade."""

    service_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("API_GATEWAY_SERVICE_PORT", "SERVICE_PORT"),
        description="HTTP port for the API Gateway",
    )
    route_service_url: str = Field(
        default="http://route-service:8002",
        validation_alias=AliasChoices(
            "API_GATEWAY_ROUTE_SERVICE_URL",
            "APIGATEWAY_ROUTE_SERVICE_URL",
            "ROUTE_SERVICE_URL",
        ),
        description="Private Route Service base URL",
    )
    fleet_service_url: str = Field(
        default="http://fleet-management-service:8003",
        validation_alias=AliasChoices(
            "API_GATEWAY_FLEET_SERVICE_URL",
            "APIGATEWAY_FLEET_SERVICE_URL",
            "FLEET_SERVICE_URL",
        ),
        description="Private Fleet Management Service base URL",
    )
    redis_url: str = Field(
        default="redis://redis:6379/0",
        validation_alias=AliasChoices(
            "API_GATEWAY_REDIS_URL",
            "APIGATEWAY_REDIS_URL",
            "REDIS_URL",
        ),
        description="Redis URL used for latest live bus snapshots",
    )
    auth_service_url: str = Field(
        default="http://auth-service:8005",
        validation_alias=AliasChoices(
            "API_GATEWAY_AUTH_SERVICE_URL",
            "APIGATEWAY_AUTH_SERVICE_URL",
            "AUTH_SERVICE_URL",
        ),
        description="Planned Auth wrapper or G4 Auth base URL",
    )

    postgres_host: str = Field(
        default="postgres",
        validation_alias=AliasChoices("API_GATEWAY_POSTGRES_HOST", "POSTGRES_HOST"),
        description="PostgreSQL host for health checks",
    )
    postgres_port: int = Field(
        default=5432,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("API_GATEWAY_POSTGRES_PORT", "POSTGRES_PORT"),
        description="PostgreSQL port for health checks",
    )
    redis_host: str = Field(
        default="redis",
        validation_alias=AliasChoices("API_GATEWAY_REDIS_HOST", "REDIS_HOST"),
        description="Redis host for health checks",
    )
    redis_port: int = Field(
        default=6379,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("API_GATEWAY_REDIS_PORT", "REDIS_PORT"),
        description="Redis port for health checks",
    )
    kafka_host: str = Field(
        default="broker",
        validation_alias=AliasChoices("API_GATEWAY_KAFKA_HOST", "KAFKA_HOST"),
        description="Kafka host for health checks",
    )
    kafka_port: int = Field(
        default=29092,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("API_GATEWAY_KAFKA_PORT", "KAFKA_PORT"),
        description="Kafka port for health checks",
    )
    influxdb_host: str = Field(
        default="influxdb",
        validation_alias=AliasChoices("API_GATEWAY_INFLUXDB_HOST", "INFLUXDB_HOST"),
        description="InfluxDB host for health checks",
    )
    influxdb_port: int = Field(
        default=8086,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("API_GATEWAY_INFLUXDB_PORT", "INFLUXDB_PORT"),
        description="InfluxDB port for health checks",
    )

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = ApiGatewaySettings()

# Backward-compatible constants used by existing service clients/tests.
ROUTE_SERVICE_URL = settings.route_service_url
FLEET_SERVICE_URL = settings.fleet_service_url
REDIS_URL = settings.redis_url
AUTH_SERVICE_URL = settings.auth_service_url
