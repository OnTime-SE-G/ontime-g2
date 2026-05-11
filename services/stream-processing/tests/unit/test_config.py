import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import StreamSettings


def test_stream_config_loads_defaults():
    settings = StreamSettings()

    assert settings.kafka_broker_url == "broker:29092"
    assert settings.kafka_raw_topic == "transport-telemetry-raw"
    assert settings.kafka_cleaned_topic == "transport-telemetry-cleaned"
    assert settings.kafka_invalid_topic == "telemetry-invalid"
    assert settings.kafka_lifecycle_topic == "trip.lifecycle"
    assert settings.route_deviation_threshold_meters == 50.0
    assert settings.redis_host == "redis"
    assert settings.redis_fleet_live_channel == "fleet:live"
    assert settings.flink_parallelism == 1


def test_stream_config_accepts_service_specific_env(monkeypatch):
    monkeypatch.setenv("STREAM_KAFKA_BROKER_URL", "kafka:9092")
    monkeypatch.setenv("STREAM_REDIS_PORT", "6380")
    monkeypatch.setenv("STREAM_FLINK_PARALLELISM", "2")

    settings = StreamSettings()

    assert settings.kafka_broker_url == "kafka:9092"
    assert settings.redis_port == 6380
    assert settings.flink_parallelism == 2
