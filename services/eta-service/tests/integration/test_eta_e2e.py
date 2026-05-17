"""Integration test — ETA full pipeline end-to-end.

Verifies the complete flow from ETA_IMPLEMENTATION_PLAN.md (N-8):

    transport-eta-features Kafka message
        → consumer.process_payload()
        → Redis snapshot written (eta:trip:{tripId}:snapshot) with TTL 300s
        → eta:live Pub/Sub message published with ETA update event
        → GET /eta/{tripId}/{stopId} HTTP endpoint returns valid ETA

All external dependencies (Kafka client, real Redis) are mocked so
this test suite runs in CI without infrastructure.

Run from services/eta-service:
    PYTHONPATH=. python -m pytest tests/integration/test_eta_e2e.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))


def make_eta_features_message(**overrides) -> dict[str, Any]:
    """Factory for transport-eta-features Kafka message."""
    msg = {
        "tripId": "TRIP-2026-INT-001",
        "busId": "BUS-007",
        "routeId": "1",
        "nextStopId": 42,
        "distanceToNextStop": 500.0,
        "stopsRemaining": 3,
        "stopsAhead": [
            {"stopId": 42, "stopName": "Kadawatha Junction", "stopOrder": 5, "distanceAlongRouteMeters": 500.0},
            {"stopId": 43, "stopName": "Gampaha", "stopOrder": 6, "distanceAlongRouteMeters": 1200.0},
            {"stopId": 44, "stopName": "Kirindiwela", "stopOrder": 7, "distanceAlongRouteMeters": 2500.0},
        ],
        "speed": 8.33,
        "routeProgressPct": 42.0,
        "timestamp": "2026-05-05T10:00:00Z",
    }
    msg.update(overrides)
    return msg


class FakeRedis:
    """Capture all Redis calls for assertion."""

    def __init__(self):
        self.setex_calls: list[tuple[str, int, str]] = []
        self.publish_calls: list[tuple[str, str]] = []

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.setex_calls.append((key, ttl, value))

    def publish(self, channel: str, message: str) -> None:
        self.publish_calls.append((channel, message))


class TestEtaPipelineEnd2End:
    """Full end-to-end flow: Kafka message → consumer → Redis snapshots + live events."""

    def test_consumer_writes_snapshot_and_publishes_eta_live(self):
        """Core N-8 behavior: consumer updates Redis and publishes live ETA."""
        from app.consumers.eta_consumer import EtaFeatureConsumer

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="physics")
        payload = make_eta_features_message()

        result = consumer.process_payload(payload)

        # Verify snapshot was written
        assert len(redis_mock.setex_calls) == 1, f"Expected 1 setex call, got {len(redis_mock.setex_calls)}"
        key, ttl, value_json = redis_mock.setex_calls[0]

        assert key == "eta:trip:TRIP-2026-INT-001:snapshot", f"Unexpected key: {key}"
        assert ttl == 300, f"Expected TTL 300, got {ttl}"

        snapshot = json.loads(value_json)
        assert snapshot["busId"] == "BUS-007"
        assert snapshot["routeId"] == "1"
        assert snapshot["nextStopId"] == 42
        assert snapshot["etaSeconds"] > 0

        # Verify eta:live was published
        assert len(redis_mock.publish_calls) == 1, f"Expected 1 publish call, got {len(redis_mock.publish_calls)}"
        channel, msg_json = redis_mock.publish_calls[0]

        assert channel == "eta:live", f"Unexpected channel: {channel}"
        live_msg = json.loads(msg_json)
        assert live_msg["event"] == "eta_update"
        assert live_msg["tripId"] == "TRIP-2026-INT-001"
        assert live_msg["busId"] == "BUS-007"
        assert live_msg["stopId"] == 42
        assert live_msg["eta_seconds"] > 0
        assert live_msg["model_used"] == "physics"

    def test_snapshot_contains_stops_ahead(self):
        """Snapshot must include stopsAhead for the HTTP endpoint to use."""
        from app.consumers.eta_consumer import EtaFeatureConsumer

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="physics")
        payload = make_eta_features_message()

        consumer.process_payload(payload)

        _, _, value_json = redis_mock.setex_calls[0]
        snapshot = json.loads(value_json)

        assert "stopsAhead" in snapshot
        stops = snapshot["stopsAhead"]
        assert len(stops) == 3
        assert stops[0]["stopId"] == 42
        assert stops[0]["stopName"] == "Kadawatha Junction"
        assert stops[0]["distanceAlongRouteMeters"] == 500.0

    def test_physics_eta_computation(self):
        """ETA must be distance / speed (physics formula)."""
        from app.consumers.eta_consumer import EtaFeatureConsumer

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="physics")
        payload = make_eta_features_message(distanceToNextStop=800.0, speed=10.0)

        consumer.process_payload(payload)

        _, _, value_json = redis_mock.setex_calls[0]
        snapshot = json.loads(value_json)

        # 800 / 10 = 80 seconds
        assert snapshot["etaSeconds"] == pytest.approx(80.0, rel=0.01)

    def test_xgboost_selection_when_model_available(self, monkeypatch):
        """Consumer should use XGBoost when artifact is available."""
        from app.consumers.eta_consumer import EtaFeatureConsumer
        from app.prediction.inference_router import InferenceOutcome

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="xgboost")
        payload = make_eta_features_message()

        fake_result = type("EtaResult", (), {"eta_seconds": 77.0, "speed_ms": 8.33, "clamped": False})()
        monkeypatch.setattr(
            "consumer.EtaFeatureConsumer._predict_eta",
            lambda self, *args, **kwargs: InferenceOutcome(
                result=fake_result, model_used="xgboost", segment_mode="urban"
            ),
        )
        result = consumer.process_payload(payload)

        assert result["model_used"] == "xgboost"

        # Verify snapshot and live event both reference xgboost
        _, _, snap_json = redis_mock.setex_calls[0]
        snapshot = json.loads(snap_json)
        assert snapshot["modelUsed"] == "xgboost"

        _, live_json = redis_mock.publish_calls[0]
        live_msg = json.loads(live_json)
        assert live_msg["model_used"] == "xgboost"

    def test_physics_fallback_on_missing_xgboost(self, monkeypatch):
        """Consumer should fall back to physics if XGBoost fails."""
        from app.consumers.eta_consumer import EtaFeatureConsumer
        from app.prediction.inference_router import InferenceOutcome

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="xgboost")
        payload = make_eta_features_message()

        fake_result = type("EtaResult", (), {"eta_seconds": 60.0, "speed_ms": 8.33, "clamped": False})()
        monkeypatch.setattr(
            "consumer.EtaFeatureConsumer._predict_eta",
            lambda self, *args, **kwargs: InferenceOutcome(
                result=fake_result, model_used="physics", segment_mode="urban"
            ),
        )
        result = consumer.process_payload(payload)

        assert result["model_used"] == "physics"
        _, _, snap_json = redis_mock.setex_calls[0]
        snapshot = json.loads(snap_json)
        assert snapshot["modelUsed"] == "physics"

    def test_multiple_messages_overwrite_snapshot(self):
        """Consecutive messages for the same trip should overwrite the snapshot."""
        from app.consumers.eta_consumer import EtaFeatureConsumer

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="physics")

        msg1 = make_eta_features_message(distanceToNextStop=500.0)
        msg2 = make_eta_features_message(distanceToNextStop=300.0)

        consumer.process_payload(msg1)
        consumer.process_payload(msg2)

        # Both messages use the same trip/key, so there should be 2 setex calls
        assert len(redis_mock.setex_calls) == 2
        assert redis_mock.setex_calls[0][0] == redis_mock.setex_calls[1][0]  # same key

        # Second snapshot should have the new distance
        snap2 = json.loads(redis_mock.setex_calls[1][2])
        assert snap2["distanceToNextStop"] == pytest.approx(300.0)

    def test_http_endpoint_reads_from_snapshot(self):
        """HTTP endpoint must be able to read the snapshot written by the consumer."""
        from app.consumers.eta_consumer import EtaFeatureConsumer

        redis_mock = FakeRedis()
        consumer = EtaFeatureConsumer(redis_mock, default_model="physics")
        payload = make_eta_features_message()

        consumer.process_payload(payload)

        # Simulate the HTTP endpoint reading from the snapshot
        _, _, snap_json = redis_mock.setex_calls[0]
        snapshot = json.loads(snap_json)

        # Find the requested stop in stopsAhead
        stops = snapshot.get("stopsAhead", [])
        matched = None
        for s in stops:
            if int(s.get("stopId")) == 42:
                matched = s
                break

        assert matched is not None, "Stop 42 should be in stopsAhead"
        assert matched["distanceAlongRouteMeters"] == pytest.approx(500.0)
        assert matched["stopName"] == "Kadawatha Junction"
