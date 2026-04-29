import pytest

from services.ingestion.config import IngestionSettings

def test_config_loads_with_defaults():
    # Because we don't have .env in the test environment, 
    # it should load defaults or fallback to OS environment variables.
    settings = IngestionSettings()
    assert settings.mqtt_broker_port == 1883
    assert settings.service_port == 8001
    assert "transport/bus/+/location" in settings.mqtt_topic_pattern
