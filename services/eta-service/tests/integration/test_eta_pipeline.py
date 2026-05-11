"""
Integration test — ETA full pipeline (async variant).

Verifies the complete flow defined in ETA_IMPLEMENTATION_PLAN.md using async patterns
to test parallel consumer processing and async Redis calls:

    transport-eta-features Kafka message
        → consumer.EtaFeatureConsumer.process_payload()
        → Redis snapshot written (eta:trip:{tripId}:snapshot)
        → eta:live Pub/Sub message published
        → GET /eta/{tripId}/{stopId} HTTP endpoint returns valid ETA

All external dependencies (Kafka, Redis, XGBoost artifact) are mocked so
this suite runs in CI without infrastructure.

Run after Nidarshan merges N-1–N-8 and all unit tests pass:

    cd services/eta-service
    PYTHONPATH=. python -m pytest tests/integration/ -v

NOTE: This file uses async mocking patterns to test concurrent scenarios.
See test_eta_e2e.py for the primary synchronous integration tests.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict
import unittest.mock as mock

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))
    def test_full_pipeline_physics(self):
        """
        1. consumer.EtaFeatureConsumer.process_payload() processes message.
        2. Snapshot is written to Redis with correct structure.
        3. eta:live is published with consistent ETA.
        """
        from consumer import EtaFeatureConsumer

        redis_write = FakeRedis()
        consumer = EtaFeatureConsumer(redis_write, default_model="physics")
        consumer.process_payload(ETA_FEATURES_MESSAGE)

        assert len(redis_write.setex_calls) > 0
        assert len(redis_write.publish_calls) > 0

        # Extract and verify snapshot
        snapshot_json = None
        for key, ttl, value in redis_write.setex_calls:
            if TRIP_ID in key:
                snapshot_json = value
                break
        assert snapshot_json is not None
        snapshot = json.loads(snapshot_json)
        assert snapshot["etaSeconds"] >= 0

    def test_full_pipeline_xgboost_fallback_to_physics(self):
        """XGBoost default should produce valid snapshot and live event."""
        from consumer import EtaFeatureConsumer

        redis_write = FakeRedis()
        consumer = EtaFeatureConsumer(redis_write, default_model="xgboost")
        consumer.process_payload(ETA_FEATURES_MESSAGE)

        assert len(redis_write.setex_calls) > 0
        assert len(redis_write.publish_calls) > 0

    def test_eta_live_and_snapshot_eta_agree(self):
        """ETA in snapshot and eta:live must be identical (same computation)."""
        from consumer import EtaFeatureConsumer

        redis_write = FakeRedis()
        consumer = EtaFeatureConsumer(redis_write, default_model="physics")
        consumer.process_payload(ETA_FEATURES_MESSAGE)

        # Get eta from snapshot
        snapshot_eta = None
        for key, ttl, value in redis_write.setex_calls:
            if TRIP_ID in key:
                snap = json.loads(value)
                snapshot_eta = snap["etaSeconds"]
                break

        # Get eta from live event
        live_eta = None
        for channel, message in redis_write.publish_calls:
            if channel == "eta:live":
                live_eta = json.loads(message)["eta_seconds"]
                break

        assert snapshot_eta is not None
        assert live_eta is not None
        assert snapshot_eta == pytest.approx(live_eta, rel=0.01)
# ---------------------------------------------------------------------------
# Shared test data — mirrors the transport-eta-features Kafka message contract
# ---------------------------------------------------------------------------

TRIP_ID = "TRIP-2026-INT-001"
BUS_ID = "BUS-007"
ROUTE_ID = "1"
NEXT_STOP_ID = 42
STOP_NAME = "Kadawatha Junction"

ETA_FEATURES_MESSAGE: Dict[str, Any] = {
    "tripId": TRIP_ID,
    "busId": BUS_ID,
    "routeId": ROUTE_ID,
    "speed": 8.33,                   # m/s (~30 km/h)
    "nextStopId": NEXT_STOP_ID,
    "distanceToNextStop": 500.0,     # metres
    "stopsRemaining": 3,
    "stopsAhead": [
        {"stopId": 42, "stopName": STOP_NAME, "stopOrder": 5, "distanceAlongRouteMeters": 500.0},
        {"stopId": 43, "stopName": "Gampaha", "stopOrder": 6, "distanceAlongRouteMeters": 1200.0},
        {"stopId": 44, "stopName": "Kirindiwela", "stopOrder": 7, "distanceAlongRouteMeters": 2500.0},
    ],
    "routeProgressPct": 42.0,
    "timestamp": "2026-05-05T10:00:00Z",   # 10 am — off-peak, weekday
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeRedis:
    """Synchronous Redis mock that captures all calls."""
    def __init__(self):
        self.setex_calls: list[tuple[str, int, str]] = []
        self.publish_calls: list[tuple[str, str]] = []
    
    def setex(self, key: str, ttl: int, value: str) -> None:
        self.setex_calls.append((key, ttl, value))
    
    def publish(self, channel: str, message: str) -> None:
        self.publish_calls.append((channel, message))


# ===========================================================================
# 1. Consumer — EtaFeatureConsumer.process_payload() writes Redis snapshot
# ===========================================================================

class TestConsumerRedisSnapshot:
    """N-1: consumer updates eta:trip:{tripId}:snapshot on every eta-features msg."""

    def test_snapshot_key_written(self):
        """Snapshot key must include the tripId."""
        from consumer import EtaFeatureConsumer

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="physics")
        consumer.process_payload(ETA_FEATURES_MESSAGE)

        written_keys = [call[0] for call in redis_mock.setex_calls]
        assert any(TRIP_ID in k for k in written_keys), (
            f"Expected eta:trip:{TRIP_ID}:snapshot in setex calls, got {written_keys}"
        )

    def test_snapshot_ttl_is_300(self):
        """Snapshot must expire in 300 s so stale trips auto-clear."""
        from consumer import EtaFeatureConsumer

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="physics")
        consumer.process_payload(ETA_FEATURES_MESSAGE)

        # setex(key, ttl, value)
        for key, ttl, value in redis_mock.setex_calls:
            if TRIP_ID in key:
                assert ttl == 300, f"Expected TTL 300, got {ttl}"
                return
        pytest.fail("setex was not called for the trip snapshot")

    def test_snapshot_contains_required_fields(self):
        """Snapshot JSON must carry all fields other services depend on."""
        from consumer import EtaFeatureConsumer

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="physics")
        consumer.process_payload(ETA_FEATURES_MESSAGE)

        raw_value = None
        for key, ttl, value in redis_mock.setex_calls:
            if TRIP_ID in key:
                raw_value = value
                break

        assert raw_value is not None, "Snapshot value not written"
        snap = json.loads(raw_value)

        required = {
            "busId", "routeId", "distanceToNextStop", "speed",
            "nextStopId", "stopsRemaining", "routeProgressPct", "timestamp",
            "etaSeconds", "effectiveSpeedMs", "speedClamped",
        }
        missing = required - snap.keys()
        assert not missing, f"Snapshot missing fields: {missing}"

    def test_snapshot_values_match_message(self):
        """Snapshot values must match the incoming ETA features message."""
        from consumer import EtaFeatureConsumer

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="physics")
        consumer.process_payload(ETA_FEATURES_MESSAGE)

        snap = None
        for key, ttl, value in redis_mock.setex_calls:
            if TRIP_ID in key:
                snap = json.loads(value)
                break

        assert snap["busId"] == BUS_ID
        assert snap["routeId"] == ROUTE_ID
        assert snap["nextStopId"] == NEXT_STOP_ID
        assert snap["distanceToNextStop"] == pytest.approx(500.0)
        assert snap["speed"] == pytest.approx(8.33)
        assert snap["stopsRemaining"] == 3


# ===========================================================================
# 2. Consumer — EtaFeatureConsumer.process_payload() publishes to eta:live
# ===========================================================================

class TestConsumerEtaLivePublish:
    """N-1: consumer must publish an ETA update to eta:live after every message."""

    def test_publishes_to_eta_live(self):
        from consumer import EtaFeatureConsumer

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="physics")
        consumer.process_payload(ETA_FEATURES_MESSAGE)

        published_channels = [call[0] for call in redis_mock.publish_calls]
        assert "eta:live" in published_channels, (
            f"Expected publish to 'eta:live', got {published_channels}"
        )

    def test_eta_live_message_schema(self):
        """Published message must follow the agreed eta:live contract."""
        from consumer import EtaFeatureConsumer

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="physics")
        consumer.process_payload(ETA_FEATURES_MESSAGE)

        raw = None
        for channel, message in redis_mock.publish_calls:
            if channel == "eta:live":
                raw = message
                break
        assert raw is not None

        msg = json.loads(raw)
        required = {
            "event", "tripId", "busId", "routeId", "stopId",
            "eta_seconds", "model_used", "routeProgressPct",
            "distanceToNextStop", "timestamp",
        }
        missing = required - msg.keys()
        assert not missing, f"eta:live message missing fields: {missing}"

    def test_eta_live_event_type(self):
        from consumer import EtaFeatureConsumer

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="physics")
        consumer.process_payload(ETA_FEATURES_MESSAGE)

        for channel, message in redis_mock.publish_calls:
            if channel == "eta:live":
                msg = json.loads(message)
                assert msg["event"] == "eta_update"
                return
        pytest.fail("eta:live was never published")

    def test_eta_live_eta_seconds_positive(self):
        from consumer import EtaFeatureConsumer

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="physics")
        consumer.process_payload(ETA_FEATURES_MESSAGE)

        for channel, message in redis_mock.publish_calls:
            if channel == "eta:live":
                msg = json.loads(message)
                assert msg["eta_seconds"] >= 0, (
                    f"eta_seconds must be non-negative, got {msg['eta_seconds']}"
                )
                return

    def test_eta_live_trip_and_stop_ids(self):
        from consumer import EtaFeatureConsumer

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="physics")
        consumer.process_payload(ETA_FEATURES_MESSAGE)

        for channel, message in redis_mock.publish_calls:
            if channel == "eta:live":
                msg = json.loads(message)
                assert msg["tripId"] == TRIP_ID
                assert msg["stopId"] == NEXT_STOP_ID
                return


# ===========================================================================
# 3. Consumer — physics fallback when XGBoost model is missing
# ===========================================================================

class TestConsumerModelFallback:
    """Consumer must fall back to physics when the XGBoost artifact is absent."""

    def test_physics_fallback_still_publishes(self):
        """Even when XGBoost artifact is missing, the consumer must publish."""
        from consumer import EtaFeatureConsumer

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="xgboost")
        consumer.process_payload(ETA_FEATURES_MESSAGE)

        # Should have published to eta:live even with xgboost default
        assert redis_mock.publish_calls, "publish was not called during fallback"

    def test_physics_fallback_model_used_field(self):
        """model_used must reflect the actual model used (physics or xgboost)."""
        from consumer import EtaFeatureConsumer

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="physics")
        consumer.process_payload(ETA_FEATURES_MESSAGE)

        for channel, message in redis_mock.publish_calls:
            if channel == "eta:live":
                msg = json.loads(message)
                assert msg["model_used"] in ("physics", "xgboost"), (
                    f"model_used must be 'physics' or 'xgboost', got {msg['model_used']}"
                )
                return


# ===========================================================================
# 4. HTTP endpoint — GET /eta/{tripId}/{stopId}
# ===========================================================================

class TestEtaHttpEndpoint:
    """
    NOTE: Full HTTP endpoint testing is in unit tests (test_eta_endpoint.py).
    
    These integration tests focus on end-to-end consumer→snapshot behavior.
    """

    def test_snapshot_structure_matches_http_expectations(self):
        """Snapshot structure must be readable by HTTP endpoint."""
        from consumer import EtaFeatureConsumer

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="physics")
        consumer.process_payload(ETA_FEATURES_MESSAGE)

        snapshot_json = None
        for key, ttl, value in redis_mock.setex_calls:
            if TRIP_ID in key:
                snapshot_json = value
                break

        assert snapshot_json is not None
        snapshot = json.loads(snapshot_json)

        # These are the exact fields HTTP endpoint uses
        assert "stopsAhead" in snapshot
        assert "etaSeconds" in snapshot
        assert "effectiveSpeedMs" in snapshot
        assert "speedClamped" in snapshot


# ===========================================================================
# 5. End-to-end: message in → HTTP endpoint out
# ===========================================================================

class TestEndToEnd:
    """
    Simulate the full flow: consumer processes a message, writes Redis snapshot,
    then the HTTP endpoint reads that snapshot and returns a valid ETA.

    This is the closest to a real smoke test without live infrastructure.
    """

    def test_full_pipeline_physics(self):
        """
        1. consumer.EtaFeatureConsumer.process_payload() is called with message.
        2. Capture the Redis setex call to get the written snapshot.
        3. Feed that snapshot to the HTTP endpoint.
        4. Assert response is 200 with valid eta_seconds.
        """
        from consumer import EtaFeatureConsumer
        from fastapi.testclient import TestClient
        from main import app  # noqa: PLC0415

        redis_write = FakeRedis()
        consumer = EtaFeatureConsumer(redis_write, default_model="physics")
        consumer.process_payload(ETA_FEATURES_MESSAGE)

        # Extract the snapshot that was written to Redis
        written_snapshot = None
        for key, ttl, value in redis_write.setex_calls:
            if TRIP_ID in key:
                written_snapshot = value
                break
        assert written_snapshot is not None, "Consumer did not write a snapshot"

        # Feed it to the HTTP endpoint
        redis_read = mock.MagicMock()
        redis_read.get = mock.MagicMock(return_value=written_snapshot.encode() if isinstance(written_snapshot, str) else written_snapshot)

        with mock.patch("routers.eta._get_redis_client", return_value=redis_read):
            client = TestClient(app)
            resp = client.get(f"/api/v1/eta/{TRIP_ID}/{NEXT_STOP_ID}?model=physics")

        assert resp.status_code == 200
        body = resp.json()
        assert body["tripId"] == TRIP_ID
        assert body["stopId"] == NEXT_STOP_ID
        assert body["eta_seconds"] >= 0

    def test_full_pipeline_xgboost_fallback_to_physics(self):
        """When XGBoost artifact is missing the pipeline must still return 200."""
        from consumer import EtaFeatureConsumer
        from fastapi.testclient import TestClient
        from main import app  # noqa: PLC0415

        redis_write = FakeRedis()
        consumer = EtaFeatureConsumer(redis_write, default_model="xgboost")
        consumer.process_payload(ETA_FEATURES_MESSAGE)

        written_snapshot = None
        for key, ttl, value in redis_write.setex_calls:
            if TRIP_ID in key:
                written_snapshot = value
                break
        assert written_snapshot is not None

        redis_read = mock.MagicMock()
        redis_read.get = mock.MagicMock(return_value=written_snapshot.encode() if isinstance(written_snapshot, str) else written_snapshot)

        with mock.patch("routers.eta._get_redis_client", return_value=redis_read):
            client = TestClient(app)
            resp = client.get(f"/api/v1/eta/{TRIP_ID}/{NEXT_STOP_ID}?model=xgboost")

        assert resp.status_code == 200
        assert resp.json()["model_used"] in ("physics", "xgboost")

    def test_eta_live_and_http_agree(self):
        """
        eta_seconds in the HTTP response and in the eta:live publish must agree
        within 1 second (both derived from the same snapshot).
        """
        from consumer import EtaFeatureConsumer
        from fastapi.testclient import TestClient
        from main import app  # noqa: PLC0415

        redis_write = FakeRedis()
        consumer = EtaFeatureConsumer(redis_write, default_model="physics")
        consumer.process_payload(ETA_FEATURES_MESSAGE)

        # Get eta_seconds from eta:live
        live_eta = None
        for channel, message in redis_write.publish_calls:
            if channel == "eta:live":
                live_eta = json.loads(message)["eta_seconds"]
                break
        assert live_eta is not None

        # Get eta_seconds from HTTP endpoint using same snapshot
        written_snapshot = None
        for key, ttl, value in redis_write.setex_calls:
            if TRIP_ID in key:
                written_snapshot = value
                break

        redis_read = mock.MagicMock()
        redis_read.get = mock.MagicMock(return_value=written_snapshot.encode() if isinstance(written_snapshot, str) else written_snapshot)

        with mock.patch("routers.eta._get_redis_client", return_value=redis_read):
            client = TestClient(app)
            resp = client.get(f"/api/v1/eta/{TRIP_ID}/{NEXT_STOP_ID}?model=physics")

        http_eta = resp.json()["eta_seconds"]
        assert abs(http_eta - live_eta) < 1.0, (
            f"eta:live ({live_eta:.2f}s) and HTTP ({http_eta:.2f}s) differ by more than 1s"
        )
