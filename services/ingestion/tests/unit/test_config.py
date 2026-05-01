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
    assert "transport/bus/+/location" in settings.mqtt_topic_pattern


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
