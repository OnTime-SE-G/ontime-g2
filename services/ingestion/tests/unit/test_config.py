from services.ingestion.app.config import IngestionSettings

def test_config_loads_with_defaults():
    settings = IngestionSettings()
    assert settings.mqtt_broker_port == 1883
    assert settings.mqtt_tls_enabled is False
    assert settings.mqtt_username is None
    assert settings.mqtt_password is None
    assert settings.mqtt_client_id == "ontime-ingestion-service"
    assert settings.mqtt_ca_cert_path is None
    assert settings.service_port == 8001
    assert settings.min_message_interval_seconds == 3.0
    assert settings.min_event_interval_seconds == 1.0
    assert settings.max_future_skew_seconds == 30.0
    assert settings.max_stale_age_seconds == 86400.0
    assert settings.kafka_trip_lifecycle_topic == "trip.lifecycle"
    assert settings.trip_cache_consumer_group == "ingestion-trip-cache"
    assert settings.require_active_trip is True
    assert settings.trip_cache_rebuild_timeout_seconds == 60.0
    assert settings.startup_buffer_max_messages == 1000
    assert settings.stateless_mode is True
    assert "transport/bus/+/location" in settings.mqtt_topic_pattern
    assert settings.mqtt_heartbeat_topic_pattern == "transport/bus/+/heartbeat"


def test_config_loads_hivemq_mqtt_options(monkeypatch):
    monkeypatch.setenv("MQTT_TLS_ENABLED", "true")
    monkeypatch.setenv("MQTT_USERNAME", "hivemq-user")
    monkeypatch.setenv("MQTT_PASSWORD", "hivemq-pass")
    monkeypatch.setenv("MQTT_CLIENT_ID", "ingestion-hivemq")
    monkeypatch.setenv("MQTT_CA_CERT_PATH", "/certs/hivemq-ca.pem")

    settings = IngestionSettings()

    assert settings.mqtt_tls_enabled is True
    assert settings.mqtt_username == "hivemq-user"
    assert settings.mqtt_password == "hivemq-pass"
    assert settings.mqtt_client_id == "ingestion-hivemq"
    assert settings.mqtt_ca_cert_path == "/certs/hivemq-ca.pem"


def test_config_loads_heartbeat_topic_option(monkeypatch):
    monkeypatch.setenv("INGESTION_MQTT_HEARTBEAT_TOPIC_PATTERN", "device/+/pulse")

    settings = IngestionSettings()

    assert settings.mqtt_heartbeat_topic_pattern == "device/+/pulse"


def test_config_loads_event_time_validation_options(monkeypatch):
    monkeypatch.setenv("INGESTION_MIN_EVENT_INTERVAL_SECONDS", "2.5")
    monkeypatch.setenv("INGESTION_MAX_FUTURE_SKEW_SECONDS", "45")
    monkeypatch.setenv("INGESTION_MAX_STALE_AGE_SECONDS", "3600")

    settings = IngestionSettings()

    assert settings.min_event_interval_seconds == 2.5
    assert settings.max_future_skew_seconds == 45.0
    assert settings.max_stale_age_seconds == 3600.0


def test_config_loads_trip_cache_options(monkeypatch):
    monkeypatch.setenv("INGESTION_KAFKA_TRIP_LIFECYCLE_TOPIC", "trip.lifecycle.dev")
    monkeypatch.setenv("INGESTION_TRIP_CACHE_CONSUMER_GROUP", "ingestion-cache-test")
    monkeypatch.setenv("INGESTION_REQUIRE_ACTIVE_TRIP", "false")
    monkeypatch.setenv("INGESTION_TRIP_CACHE_REBUILD_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("INGESTION_STARTUP_BUFFER_MAX_MESSAGES", "25")

    settings = IngestionSettings()

    assert settings.kafka_trip_lifecycle_topic == "trip.lifecycle.dev"
    assert settings.trip_cache_consumer_group == "ingestion-cache-test"
    assert settings.require_active_trip is False
    assert settings.trip_cache_rebuild_timeout_seconds == 12.5
    assert settings.startup_buffer_max_messages == 25
