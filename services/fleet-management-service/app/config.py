from pathlib import Path
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Path discovery
CURRENT_FILE = Path(__file__).resolve()

# In Docker, we might only have 2 parents (/app/app/config.py -> /app/app -> /app)
# In local dev, we have 4 (/services/fleet-service/app/config.py -> ... -> root)
try:
    REPO_ROOT = CURRENT_FILE.parents[3]
    ENV_FILES = (
        str(REPO_ROOT / "docker" / ".env"),
        str(REPO_ROOT / "docker" / ".env.example"),
    )
except (IndexError, ValueError):
    # Fallback for Docker or unusual structures
    REPO_ROOT = CURRENT_FILE.parents[1]
    ENV_FILES = ()

class FleetSettings(BaseSettings):
    """Configuration for the fleet management service."""

    database_url: str = Field(
        default="postgresql://postgres:postgres@postgres:5432/fleet_db",
        validation_alias=AliasChoices("FLEET_DATABASE_URL", "DATABASE_URL"),
    )

    kafka_broker_url: str = Field(
        default="broker:29092",
        validation_alias=AliasChoices("FLEET_KAFKA_BROKER_URL", "KAFKA_BROKER_URL"),
    )

    kafka_trip_lifecycle_topic: str = Field(
        default="trip.lifecycle",
        validation_alias=AliasChoices("FLEET_KAFKA_TRIP_LIFECYCLE_TOPIC", "KAFKA_TRIP_LIFECYCLE_TOPIC"),
    )

    route_service_url: str = Field(
        default="http://route-service:8002",
        validation_alias=AliasChoices("ROUTE_SERVICE_URL"),
    )

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

settings = FleetSettings()
