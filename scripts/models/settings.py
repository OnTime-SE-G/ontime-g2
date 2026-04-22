# scripts/models/settings.py

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/transport"

    # Files
    kml_file: str = "data/moratuwa_kadawatha.kml"

    # Route Seeding
    route_name: str = "Moratuwa to Kadawatha"

    # Kafka / AutoMQ / Redpanda
    kafka_bootstrap_servers: str = "localhost:9092"
    telemetry_topic: str = "transport-telemetry-raw"

    # GPS Simulator
    bus_id: str = "BUS_001"
    trip_id: str = "TRIP_001"
    min_interval_seconds: int = 3
    max_interval_seconds: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


settings = Settings()