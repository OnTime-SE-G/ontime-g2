import threading
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import services.ingestion.app.health as health_module
from services.ingestion.app.metrics import MetricsCollector


class TestMetricsCollectorCore:
    def test_increment_received(self):
        collector = MetricsCollector()
        collector.increment_received()
        collector.increment_received()
        assert collector.get_snapshot()["messages_received"] == 2

    def test_increment_validated(self):
        collector = MetricsCollector()
        collector.increment_validated()
        assert collector.get_snapshot()["messages_validated"] == 1

    def test_record_heartbeat_status(self):
        collector = MetricsCollector()
        timestamp = datetime.now(timezone.utc)

        collector.record_heartbeat(
            bus_id="1",
            timestamp=timestamp,
        )

        snapshot = collector.get_snapshot()
        assert snapshot["heartbeat_messages_received"] == 1
        assert snapshot["heartbeat_messages_invalid"] == 0
        assert snapshot["latest_heartbeat_by_bus"]["1"] == timestamp.isoformat()
        assert snapshot["heartbeat_age_seconds_by_bus"]["1"] >= 0

    def test_increment_invalid_heartbeat(self):
        collector = MetricsCollector()

        collector.increment_invalid_heartbeat()

        assert collector.get_snapshot()["heartbeat_messages_invalid"] == 1

    def test_increment_rejected_types(self):
        collector = MetricsCollector()
        collector.increment_rejected("JSON_PARSE")
        collector.increment_rejected("MISSING_TIMESTAMP")
        collector.increment_rejected("SCHEMA_VALIDATION")
        collector.increment_rejected("GEO_BOUNDS")
        collector.increment_rejected("DUPLICATE")
        collector.increment_rejected("RATE_LIMIT")
        collector.increment_rejected("RATE_LIMIT_EVENT_TIME")
        collector.increment_rejected("SEQUENCE_ERROR")
        collector.increment_rejected("FUTURE_TIMESTAMP")
        collector.increment_rejected("STALE_REPLAY")
        collector.increment_rejected("INACTIVE_TRIP")
        collector.increment_rejected("TRIP_CACHE_REBUILDING")

        snapshot = collector.get_snapshot()
        assert snapshot["messages_rejected_json"] == 1
        assert snapshot["messages_rejected_missing_timestamp"] == 1
        assert snapshot["messages_rejected_schema"] == 1
        assert snapshot["messages_rejected_geo"] == 1
        assert snapshot["messages_rejected_duplicate"] == 1
        assert snapshot["messages_rejected_inactive_trip"] == 1
        assert snapshot["messages_rejected_trip_cache_rebuilding"] == 1
        assert snapshot["messages_rejected_rate_limit"] == 1
        assert snapshot["messages_rejected_rate_limit_event_time"] == 1
        assert snapshot["messages_rejected_sequence"] == 1
        assert snapshot["messages_rejected_future_timestamp"] == 1
        assert snapshot["messages_rejected_stale_replay"] == 1
        assert snapshot["messages_rejected"] == 12

    def test_unknown_rejection_type_does_not_increment_totals(self):
        collector = MetricsCollector()
        collector.increment_rejected("UNKNOWN")
        assert collector.get_snapshot()["messages_rejected"] == 0

    def test_thread_safe_counters(self):
        collector = MetricsCollector()

        def increment_many():
            for _ in range(100):
                collector.increment_received()
                collector.increment_validated()

        threads = [threading.Thread(target=increment_many) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        snapshot = collector.get_snapshot()
        assert snapshot["messages_received"] == 500
        assert snapshot["messages_validated"] == 500

    def test_uptime_calculation(self):
        collector = MetricsCollector()
        time.sleep(0.05)
        snapshot = collector.get_snapshot()
        assert snapshot["uptime_seconds"] >= 0.05

    def test_broker_status(self):
        collector = MetricsCollector()
        assert collector.kafka_broker_up is False
        assert collector.mqtt_broker_up is False

        collector.kafka_broker_up = True
        snapshot = collector.get_snapshot()
        assert snapshot["kafka_broker_up"] is True
        assert snapshot["mqtt_broker_up"] is False

    def test_update_trip_cache_status(self):
        collector = MetricsCollector()
        collector.update_trip_cache(
            status="ready",
            active_trip_count=3,
            last_lifecycle_timestamp="2026-05-02T10:00:00+00:00",
        )

        snapshot = collector.get_snapshot()
        assert snapshot["trip_cache_status"] == "ready"
        assert snapshot["active_trip_count"] == 3
        assert snapshot["last_trip_lifecycle_time"] == "2026-05-02T10:00:00+00:00"

    def test_snapshot_consistency(self):
        collector = MetricsCollector()
        collector.increment_received()
        collector.increment_validated()
        collector.increment_rejected("JSON_PARSE")

        snapshot = collector.get_snapshot()
        assert snapshot["messages_received"] == 1
        assert snapshot["messages_validated"] == 1
        assert snapshot["messages_rejected"] == 1
        assert snapshot["messages_rejected_json"] == 1

    def test_total_rejected_includes_all_types(self):
        collector = MetricsCollector()
        collector.increment_rejected("JSON_PARSE")
        collector.increment_rejected("SCHEMA_VALIDATION")
        collector.increment_rejected("GEO_BOUNDS")
        collector.increment_rejected("MISSING_TIMESTAMP")
        collector.increment_rejected("RATE_LIMIT_EVENT_TIME")
        collector.increment_rejected("FUTURE_TIMESTAMP")
        collector.increment_rejected("STALE_REPLAY")
        collector.increment_rejected("INACTIVE_TRIP")
        collector.increment_rejected("TRIP_CACHE_REBUILDING")
        assert collector.get_snapshot()["messages_rejected"] == 9


@pytest.fixture
def health_client(monkeypatch):
    collector = MetricsCollector()
    monkeypatch.setattr(health_module, "metrics", collector)
    app = health_module.create_app()
    return TestClient(app), collector


class TestHealthEndpoints:
    def test_health_endpoint_imports(self):
        assert callable(health_module.create_app)

    def test_create_app_returns_fastapi_app(self):
        app = health_module.create_app()
        assert hasattr(app, "routes")

    def test_health_endpoint_routes_exist(self):
        app = health_module.create_app()
        routes = [route.path for route in app.routes]
        assert "/health" in routes
        assert "/health/live" in routes
        assert "/health/ready" in routes
        assert "/metrics" in routes

    def test_ready_endpoint_returns_503_when_dependencies_down(self, health_client):
        client, collector = health_client
        collector.kafka_broker_up = False
        collector.mqtt_broker_up = False

        response = client.get("/health/ready")

        assert response.status_code == 503
        assert response.json()["status"] == "degraded"

    def test_ready_endpoint_returns_200_when_dependencies_are_up(self, health_client):
        client, collector = health_client
        collector.kafka_broker_up = True
        collector.mqtt_broker_up = True
        collector.increment_received()
        collector.increment_validated()

        response = client.get("/health/ready")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "healthy"
        assert payload["dependencies"]["kafka_broker"] == "up"
        assert payload["dependencies"]["mqtt_broker"] == "up"
        assert payload["counters"]["messages_received"] == 1
        assert payload["counters"]["messages_validated"] == 1

    def test_health_endpoint_returns_summary_payload(self, health_client):
        client, collector = health_client
        collector.kafka_broker_up = True
        collector.mqtt_broker_up = False
        collector.increment_received()
        collector.increment_rejected("JSON_PARSE")

        response = client.get("/health")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "degraded"
        assert payload["service"] == "ingestion-service"
        assert payload["dependencies"]["kafka_broker"] == "up"
        assert payload["dependencies"]["mqtt_broker"] == "down"
        assert payload["dependencies"]["trip_cache"] == "unknown"
        assert payload["counters"]["messages_received"] == 1
        assert payload["counters"]["messages_rejected"] == 1
        assert payload["counters"]["heartbeats_received"] == 0
        assert payload["counters"]["heartbeats_invalid"] == 0
        assert payload["counters"]["active_trip_count"] == 0
        assert payload["device_status"]["latest_heartbeat_by_bus"] == {}

    def test_live_endpoint_returns_200(self, health_client):
        client, _ = health_client
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_metrics_endpoint_returns_plain_text_prometheus_payload(self, health_client):
        client, collector = health_client
        collector.kafka_broker_up = True
        collector.mqtt_broker_up = True
        collector.increment_received()
        collector.increment_validated()
        collector.record_heartbeat(bus_id="1", timestamp=datetime.now(timezone.utc))
        collector.increment_rejected("RATE_LIMIT")

        response = client.get("/metrics")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        body = response.text
        assert "ingestion_messages_received_total 1" in body
        assert "ingestion_messages_validated_total 1" in body
        assert "ingestion_heartbeat_messages_received_total 1" in body
        assert "ingestion_heartbeat_messages_invalid_total 0" in body
        assert 'ingestion_heartbeat_age_seconds{bus_id="1"}' in body
        assert 'ingestion_messages_rejected_total{reason="RATE_LIMIT"} 1' in body
        assert 'ingestion_messages_rejected_total{reason="INACTIVE_TRIP"} 0' in body
        assert 'ingestion_messages_rejected_total{reason="TRIP_CACHE_REBUILDING"} 0' in body
        assert 'ingestion_messages_rejected_total{reason="RATE_LIMIT_EVENT_TIME"} 0' in body
        assert 'ingestion_messages_rejected_total{reason="FUTURE_TIMESTAMP"} 0' in body
        assert 'ingestion_messages_rejected_total{reason="STALE_REPLAY"} 0' in body
        assert 'ingestion_messages_rejected_total{reason="MISSING_TIMESTAMP"} 0' in body
        assert "ingestion_kafka_broker_up 1" in body
        assert "ingestion_mqtt_broker_up 1" in body

    def test_start_health_server_runs_uvicorn_with_expected_arguments(self):
        with patch("logging.getLogger", return_value=MagicMock()) as get_logger:
            with patch("uvicorn.run") as mock_run:
                health_module.start_health_server()

        get_logger.assert_any_call("uvicorn.access")
        mock_run.assert_called_once_with(
            health_module.app,
            host="0.0.0.0",
            port=health_module.settings.service_port,
            log_level="info",
        )
