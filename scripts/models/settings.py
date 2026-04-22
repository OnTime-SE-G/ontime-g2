# scripts/models/settings.py

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    postgres_user: str = Field(default="postgres", validation_alias="POSTGRES_USER")
    postgres_password: str = Field(default="postgres", validation_alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="ontime_db", validation_alias="POSTGRES_DB")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_host: str = Field(default="postgres", validation_alias="POSTGRES_HOST")
    database_url: str = Field(default="", validation_alias="DATABASE_URL")

    # Files
    kml_file: str = Field(default="data/moratuwa_kadawatha.kml", validation_alias="KML_FILE")

    # Route Seeding
    route_name: str = Field(default="Moratuwa to Kadawatha", validation_alias="ROUTE_NAME")

    # Kafka / AutoMQ / Redpanda
    kafka_bootstrap_servers: str = Field(default="broker:29092", validation_alias="KAFKA_BROKER_URL")
    telemetry_topic: str = Field(default="transport-telemetry-raw", validation_alias="TELEMETRY_TOPIC")

    # GPS Simulator
    bus_id: str = Field(default="BUS_001", validation_alias="BUS_ID")
    trip_id: str = Field(default="TRIP_001", validation_alias="TRIP_ID")
    min_interval_seconds: int = Field(default=3, validation_alias="MIN_INTERVAL_SECONDS")
    max_interval_seconds: int = Field(default=5, validation_alias="MAX_INTERVAL_SECONDS")

    model_config = SettingsConfigDict(
        env_file="docker/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @model_validator(mode="after")
    def build_database_url(self):
        if self.database_url and "${" not in self.database_url:
            return self

        self.database_url = (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        return self


settings = Settings()
