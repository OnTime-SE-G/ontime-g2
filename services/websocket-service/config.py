from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


try:
    REPO_ROOT = Path(__file__).resolve().parents[2]
    ENV_FILES = (
        str(REPO_ROOT / "docker" / ".env"),
        str(REPO_ROOT / "docker" / ".env.example"),
    )
except (IndexError, ValueError):
    # Fallback for Docker or unusual structures
    REPO_ROOT = Path(__file__).resolve().parents[1]
    ENV_FILES = ()


class WebSocketSettings(BaseSettings):
    """Configuration for the WebSocket Service."""

    service_port: int = Field(
        default=8004,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("WEBSOCKET_SERVICE_PORT", "SERVICE_PORT"),
        description="HTTP/WebSocket port",
    )
    redis_url: str = Field(
        default="redis://redis:6379",
        validation_alias=AliasChoices("WEBSOCKET_REDIS_URL", "REDIS_URL"),
        description="Redis URL for live Pub/Sub",
    )
    fleet_channel: str = Field(
        default="fleet:live",
        validation_alias=AliasChoices("WEBSOCKET_FLEET_CHANNEL", "FLEET_CHANNEL"),
        description="Redis channel for live fleet positions",
    )
    eta_channel: str = Field(
        default="eta:live",
        validation_alias=AliasChoices("WEBSOCKET_ETA_CHANNEL", "ETA_CHANNEL"),
        description="Redis channel for live ETA updates",
    )

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = WebSocketSettings()
