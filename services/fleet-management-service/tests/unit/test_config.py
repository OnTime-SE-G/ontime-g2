from app.config import FleetSettings


def test_fleet_config_loads_defaults():
    settings = FleetSettings()

    assert settings.service_port == 8003
    assert settings.kafka_broker_url == "broker:29092"
    assert settings.kafka_trip_lifecycle_topic == "trip.lifecycle"
    assert settings.route_service_url == "http://route-service:8002"
    assert settings.route_service_timeout_seconds == 3.0


def test_fleet_config_accepts_service_specific_env(monkeypatch):
    monkeypatch.setenv("FLEET_DATABASE_URL", "postgresql://fleet:secret@db:5432/fleet")
    monkeypatch.setenv("FLEET_KAFKA_BROKER_URL", "kafka:9092")
    monkeypatch.setenv("FLEET_ROUTE_SERVICE_URL", "http://routes:8002")

    settings = FleetSettings()

    assert settings.database_url == "postgresql://fleet:secret@db:5432/fleet"
    assert settings.kafka_broker_url == "kafka:9092"
    assert settings.route_service_url == "http://routes:8002"
