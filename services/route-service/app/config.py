from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILES = (
    str(REPO_ROOT / "docker" / ".env"),
    str(REPO_ROOT / "docker" / ".env.example"),
)


class RouteSettings(BaseSettings):
    """Configuration for the Route Service."""

    service_port: int = Field(
        default=8002,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("ROUTE_SERVICE_PORT", "SERVICE_PORT"),
        description="HTTP port for Route Service",
    )
    database_url: str = Field(
        default="postgresql://postgres:postgres@postgres:5432/ontime_db",
        validation_alias=AliasChoices("ROUTE_DATABASE_URL", "DATABASE_URL"),
        description="PostgreSQL/PostGIS connection URL for route data",
    )

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = RouteSettings()
