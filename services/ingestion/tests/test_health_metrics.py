"""
Test suite for Phase 6: Health and Metrics Endpoints
Tests the metrics collector and health/metrics endpoints.
"""

import pytest
import threading
import time
from services.ingestion.metrics import MetricsCollector


class TestMetricsCollectorCore:
    """Test MetricsCollector functionality and thread-safety."""

    def test_increment_received(self):
        """Test incrementing received counter."""
        mc = MetricsCollector()
        mc.increment_received()
        mc.increment_received()
        assert mc.get_snapshot()["messages_received"] == 2

    def test_increment_validated(self):
        """Test incrementing validated counter."""
        mc = MetricsCollector()
        mc.increment_validated()
        assert mc.get_snapshot()["messages_validated"] == 1

    def test_increment_rejected_types(self):
        """Test incrementing rejection counters by type."""
        mc = MetricsCollector()
        mc.increment_rejected("JSON_PARSE")
        mc.increment_rejected("SCHEMA_VALIDATION")
        mc.increment_rejected("GEO_BOUNDS")
        mc.increment_rejected("DUPLICATE")
        mc.increment_rejected("RATE_LIMIT")
        mc.increment_rejected("SEQUENCE_ERROR")

        snapshot = mc.get_snapshot()
        assert snapshot["messages_rejected_json"] == 1
        assert snapshot["messages_rejected_schema"] == 1
        assert snapshot["messages_rejected_geo"] == 1
        assert snapshot["messages_rejected_duplicate"] == 1
        assert snapshot["messages_rejected_rate_limit"] == 1
        assert snapshot["messages_rejected_sequence"] == 1
        assert snapshot["messages_rejected"] == 6

    def test_thread_safe_counters(self):
        """Test thread-safety with concurrent increments."""
        mc = MetricsCollector()

        def increment_many():
            for _ in range(100):
                mc.increment_received()
                mc.increment_validated()

        threads = [threading.Thread(target=increment_many) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        snapshot = mc.get_snapshot()
        assert snapshot["messages_received"] == 500  # 5 threads * 100
        assert snapshot["messages_validated"] == 500

    def test_uptime_calculation(self):
        """Test uptime is calculated correctly."""
        mc = MetricsCollector()
        time.sleep(0.05)
        snapshot = mc.get_snapshot()
        assert snapshot["uptime_seconds"] >= 0.05

    def test_broker_status(self):
        """Test broker status tracking."""
        mc = MetricsCollector()
        assert mc.kafka_broker_up is True
        assert mc.mqtt_broker_up is True

        mc.kafka_broker_up = False
        snapshot = mc.get_snapshot()
        assert snapshot["kafka_broker_up"] is False
        assert snapshot["mqtt_broker_up"] is True

    def test_snapshot_consistency(self):
        """Test that snapshot is consistent and thread-safe."""
        mc = MetricsCollector()
        mc.increment_received()
        mc.increment_validated()
        mc.increment_rejected("JSON_PARSE")

        snapshot = mc.get_snapshot()
        assert snapshot["messages_received"] == 1
        assert snapshot["messages_validated"] == 1
        assert snapshot["messages_rejected"] == 1
        assert snapshot["messages_rejected_json"] == 1

    def test_total_rejected_includes_all_types(self):
        """Test that total rejected sums all rejection types."""
        mc = MetricsCollector()
        mc.increment_rejected("JSON_PARSE")
        mc.increment_rejected("SCHEMA_VALIDATION")
        mc.increment_rejected("GEO_BOUNDS")

        snapshot = mc.get_snapshot()
        assert snapshot["messages_rejected"] == 3


class TestHealthEndpointIntegration:
    """Integration tests for health endpoint."""

    def test_health_endpoint_imports(self):
        """Test that health module can be imported."""
        from services.ingestion.health import create_app
        assert callable(create_app)

    def test_create_app_returns_fastapi_app(self):
        """Test that create_app returns a FastAPI app."""
        from services.ingestion.health import create_app
        app = create_app()
        assert hasattr(app, "routes")

    def test_health_endpoint_routes_exist(self):
        """Test that health and metrics routes are registered."""
        from services.ingestion.health import create_app
        app = create_app()
        routes = [route.path for route in app.routes]
        assert "/health" in routes
        assert "/metrics" in routes
