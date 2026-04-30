from services.ingestion.app.config import IngestionSettings

def test_config_loads_with_defaults():
    settings = IngestionSettings()
    assert settings.mqtt_broker_port == 1883
    assert settings.service_port == 8001
    assert settings.min_message_interval_seconds == 1.0
    assert "transport/bus/+/location" in settings.mqtt_topic_pattern
