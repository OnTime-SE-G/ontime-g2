import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import AnomalySettings


def test_anomaly_config_loads_defaults():
    settings = AnomalySettings()

    assert settings.service_port == 8006
    assert settings.kafka_broker_url == "broker:29092"
    assert settings.kafka_cleaned_topic == "transport-telemetry-cleaned"
    assert settings.kafka_dlq_topic == "transport-telemetry-dlq"
    assert settings.kafka_anomaly_topic == "transport-anomaly-alerts"
    assert settings.kafka_cleaned_group_id == "anomaly-service-group"
    assert settings.anomaly_database_url.endswith("/anomaly_db")
    assert settings.route_service_url == "http://route-service:8002"
    assert settings.redis_host == "redis"
    assert settings.redis_port == 6379
    assert settings.redis_anomaly_live_channel == "anomaly:live"
    assert settings.off_route_distance_threshold_m == 50.0
    assert settings.off_route_streak_window_seconds == 5
    assert settings.persistent_off_route_threshold == 3
    assert settings.sliding_window_size == 20
    assert settings.sliding_window_min_size == 10
    assert settings.isolation_forest_artifact_path.endswith("isolation_forest.joblib")


def test_anomaly_config_accepts_service_specific_env(monkeypatch):
    monkeypatch.setenv("ANOMALY_KAFKA_BROKER_URL", "kafka:9092")
    monkeypatch.setenv("ANOMALY_KAFKA_DLQ_GROUP_ID", "dlq-test")
    monkeypatch.setenv("ANOMALY_ROUTE_REFRESH_INTERVAL_SECONDS", "30")
    monkeypatch.setenv("ANOMALY_SLIDING_WINDOW_SIZE", "12")
    monkeypatch.setenv("ANOMALY_SLIDING_WINDOW_MIN_SIZE", "6")

    settings = AnomalySettings()

    assert settings.kafka_broker_url == "kafka:9092"
    assert settings.kafka_dlq_group_id == "dlq-test"
    assert settings.route_refresh_interval_seconds == 30
    assert settings.sliding_window_size == 12
    assert settings.sliding_window_min_size == 6
