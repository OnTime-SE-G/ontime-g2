"""
Integration test — ETA full pipeline.

Verifies the complete flow defined in ETA_IMPLEMENTATION_PLAN.md:

    gps-cleaned Kafka message
        → consumer.handle_message()
        → Redis snapshot written (eta:trip:{tripId}:snapshot)
        → eta:live Pub/Sub message published
        → GET /eta/{tripId}/{stopId} HTTP endpoint returns valid ETA

All external dependencies (Kafka, Redis, XGBoost artifact) are mocked so
this suite runs in CI without infrastructure.

Run after Nidarshan merges N-1–N-8 and all unit tests pass:

    cd services/eta-service
    PYTHONPATH=. python -m pytest tests/integration/ -v
"""

from __future__ import annotations

import datetime
import json
import unittest.mock as mock
from typing import Any, Dict

import pytest


# ---------------------------------------------------------------------------
# Shared test data — mirrors the gps-cleaned Kafka message contract
# ---------------------------------------------------------------------------

TRIP_ID = "TRIP-2026-INT-001"
BUS_ID = "BUS-007"
ROUTE_ID = "1"
NEXT_STOP_ID = 42
STOP_NAME = "Kadawatha Junction"

GPS_CLEANED_MESSAGE: Dict[str, Any] = {
    "tripId": TRIP_ID,
    "busId": BUS_ID,
    "routeId": ROUTE_ID,
    "lat": 7.003,
    "lon": 80.121,
    "speed": 8.33,                   # m/s (~30 km/h)
    "nextStopId": NEXT_STOP_ID,
    "distanceToNextStop": 500.0,     # metres
    "stopsRemaining": 3,
    "stopsAhead": [
        {"stopId": 42, "stopName": STOP_NAME,   "distanceFromBus": 500.0},
        {"stopId": 43, "stopName": "Gampaha",   "distanceFromBus": 1200.0},
        {"stopId": 44, "stopName": "Kirindiwela","distanceFromBus": 2500.0},
    ],
    "routeProgressPct": 42.0,
    "timestamp": "2026-05-05T10:00:00Z",   # 10 am — off-peak, weekday
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_redis_mock():
    """Return a MagicMock that behaves like redis.asyncio.Redis."""
    r = mock.AsyncMock()
    r.setex = mock.AsyncMock(return_value=True)
    r.get = mock.AsyncMock(return_value=None)
    r.publish = mock.AsyncMock(return_value=1)
    return r


# ===========================================================================
# 1. Consumer — handle_message() writes Redis snapshot
# ===========================================================================

class TestConsumerRedisSnapshot:
    """N-1: consumer updates eta:trip:{tripId}:snapshot on every gps-cleaned msg."""

    @pytest.fixture
    def redis_mock(self):
        return _make_redis_mock()

    @pytest.mark.asyncio
    async def test_snapshot_key_written(self, redis_mock):
        """Snapshot key must include the tripId."""
        from consumer import handle_message  # noqa: PLC0415

        await handle_message(GPS_CLEANED_MESSAGE, redis_mock)

        written_keys = [call.args[0] for call in redis_mock.setex.call_args_list]
        assert any(TRIP_ID in k for k in written_keys), (
            f"Expected eta:trip:{TRIP_ID}:snapshot in setex calls, got {written_keys}"
        )

    @pytest.mark.asyncio
    async def test_snapshot_ttl_is_300(self, redis_mock):
        """Snapshot must expire in 300 s so stale trips auto-clear."""
        from consumer import handle_message  # noqa: PLC0415

        await handle_message(GPS_CLEANED_MESSAGE, redis_mock)

        # setex(key, ttl, value)
        for call in redis_mock.setex.call_args_list:
            key = call.args[0]
            if TRIP_ID in key:
                ttl = call.args[1]
                assert ttl == 300, f"Expected TTL 300, got {ttl}"
                return
        pytest.fail("setex was not called for the trip snapshot")

    @pytest.mark.asyncio
    async def test_snapshot_contains_required_fields(self, redis_mock):
        """Snapshot JSON must carry all fields other services depend on."""
        from consumer import handle_message  # noqa: PLC0415

        await handle_message(GPS_CLEANED_MESSAGE, redis_mock)

        raw_value = None
        for call in redis_mock.setex.call_args_list:
            key = call.args[0]
            if TRIP_ID in key:
                raw_value = call.args[2]
                break

        assert raw_value is not None, "Snapshot value not written"
        snap = json.loads(raw_value)

        required = {
            "busId", "routeId", "distanceToNextStop", "speed",
            "nextStopId", "stopsRemaining", "routeProgressPct", "timestamp",
        }
        missing = required - snap.keys()
        assert not missing, f"Snapshot missing fields: {missing}"

    @pytest.mark.asyncio
    async def test_snapshot_values_match_message(self, redis_mock):
        """Snapshot values must match the incoming GPS message."""
        from consumer import handle_message  # noqa: PLC0415

        await handle_message(GPS_CLEANED_MESSAGE, redis_mock)

        snap = None
        for call in redis_mock.setex.call_args_list:
            if TRIP_ID in call.args[0]:
                snap = json.loads(call.args[2])
                break

        assert snap["busId"] == BUS_ID
        assert snap["routeId"] == ROUTE_ID
        assert snap["nextStopId"] == NEXT_STOP_ID
        assert snap["distanceToNextStop"] == pytest.approx(500.0)
        assert snap["speed"] == pytest.approx(8.33)
        assert snap["stopsRemaining"] == 3


# ===========================================================================
# 2. Consumer — handle_message() publishes to eta:live
# ===========================================================================

class TestConsumerEtaLivePublish:
    """N-1: consumer must publish an ETA update to eta:live after every message."""

    @pytest.fixture
    def redis_mock(self):
        return _make_redis_mock()

    @pytest.mark.asyncio
    async def test_publishes_to_eta_live(self, redis_mock):
        from consumer import handle_message  # noqa: PLC0415

        await handle_message(GPS_CLEANED_MESSAGE, redis_mock)

        published_channels = [call.args[0] for call in redis_mock.publish.call_args_list]
        assert "eta:live" in published_channels, (
            f"Expected publish to 'eta:live', got {published_channels}"
        )

    @pytest.mark.asyncio
    async def test_eta_live_message_schema(self, redis_mock):
        """Published message must follow the agreed eta:live contract."""
        from consumer import handle_message  # noqa: PLC0415

        await handle_message(GPS_CLEANED_MESSAGE, redis_mock)

        raw = None
        for call in redis_mock.publish.call_args_list:
            if call.args[0] == "eta:live":
                raw = call.args[1]
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

    @pytest.mark.asyncio
    async def test_eta_live_event_type(self, redis_mock):
        from consumer import handle_message  # noqa: PLC0415

        await handle_message(GPS_CLEANED_MESSAGE, redis_mock)

        for call in redis_mock.publish.call_args_list:
            if call.args[0] == "eta:live":
                msg = json.loads(call.args[1])
                assert msg["event"] == "eta_update"
                return
        pytest.fail("eta:live was never published")

    @pytest.mark.asyncio
    async def test_eta_live_eta_seconds_positive(self, redis_mock):
        from consumer import handle_message  # noqa: PLC0415

        await handle_message(GPS_CLEANED_MESSAGE, redis_mock)

        for call in redis_mock.publish.call_args_list:
            if call.args[0] == "eta:live":
                msg = json.loads(call.args[1])
                assert msg["eta_seconds"] >= 0, (
                    f"eta_seconds must be non-negative, got {msg['eta_seconds']}"
                )
                return

    @pytest.mark.asyncio
    async def test_eta_live_trip_and_stop_ids(self, redis_mock):
        from consumer import handle_message  # noqa: PLC0415

        await handle_message(GPS_CLEANED_MESSAGE, redis_mock)

        for call in redis_mock.publish.call_args_list:
            if call.args[0] == "eta:live":
                msg = json.loads(call.args[1])
                assert msg["tripId"] == TRIP_ID
                assert msg["stopId"] == NEXT_STOP_ID
                return


# ===========================================================================
# 3. Consumer — physics fallback when XGBoost model is missing
# ===========================================================================

class TestConsumerModelFallback:
    """Consumer must fall back to physics when the XGBoost artifact is absent."""

    @pytest.fixture
    def redis_mock(self):
        return _make_redis_mock()

    @pytest.mark.asyncio
    async def test_physics_fallback_still_publishes(self, redis_mock):
        """Even when XGBoost artifact is missing, the consumer must publish."""
        from consumer import handle_message  # noqa: PLC0415

        with mock.patch("models.ml_eta_xgb._load_model", side_effect=FileNotFoundError):
            await handle_message(GPS_CLEANED_MESSAGE, redis_mock)

        assert redis_mock.publish.called, "publish was not called during physics fallback"

    @pytest.mark.asyncio
    async def test_physics_fallback_model_used_field(self, redis_mock):
        """model_used must be 'physics' when the artifact is missing."""
        from consumer import handle_message  # noqa: PLC0415

        with mock.patch("models.ml_eta_xgb._load_model", side_effect=FileNotFoundError):
            await handle_message(GPS_CLEANED_MESSAGE, redis_mock)

        for call in redis_mock.publish.call_args_list:
            if call.args[0] == "eta:live":
                msg = json.loads(call.args[1])
                assert msg["model_used"] == "physics"
                return


# ===========================================================================
# 4. HTTP endpoint — GET /eta/{tripId}/{stopId}
# ===========================================================================

class TestEtaHttpEndpoint:
    """N-3 / N-7: on-demand HTTP endpoint behaviour."""

    def _build_snapshot(self, distance=500.0, speed=8.33, stops_remaining=3):
        return json.dumps({
            "busId": BUS_ID,
            "routeId": ROUTE_ID,
            "distanceToNextStop": distance,
            "speed": speed,
            "nextStopId": NEXT_STOP_ID,
            "stopsRemaining": stops_remaining,
            "routeProgressPct": 42.0,
            "stopsAhead": GPS_CLEANED_MESSAGE["stopsAhead"],
            "timestamp": "2026-05-05T10:00:00Z",
        })

    def _get_client(self, snapshot_json):
        """Return a TestClient with Redis mocked to return snapshot_json."""
        from fastapi.testclient import TestClient
        from main import app  # noqa: PLC0415

        redis_mock = mock.AsyncMock()
        redis_mock.get = mock.AsyncMock(return_value=snapshot_json)

        with mock.patch("routers.eta.get_redis", return_value=redis_mock):
            return TestClient(app)

    def test_200_with_valid_snapshot(self):
        """Valid trip + stop that exists in stopsAhead → 200 with all required fields."""
        client = self._get_client(self._build_snapshot())
        resp = client.get(f"/eta/{TRIP_ID}/{NEXT_STOP_ID}")
        assert resp.status_code == 200

        body = resp.json()
        assert body["tripId"] == TRIP_ID
        assert body["stopId"] == NEXT_STOP_ID
        assert body["eta_seconds"] >= 0
        assert "model_used" in body
        assert "distance_m" in body
        assert "speed_ms" in body
        assert "clamped" in body
        assert "timestamp" in body

    def test_503_when_no_snapshot(self):
        """Trip with no Redis snapshot → 503 Service Unavailable."""
        from fastapi.testclient import TestClient
        from main import app  # noqa: PLC0415

        redis_mock = mock.AsyncMock()
        redis_mock.get = mock.AsyncMock(return_value=None)   # nothing in Redis

        with mock.patch("routers.eta.get_redis", return_value=redis_mock):
            client = TestClient(app)

        resp = client.get(f"/eta/TRIP-NONEXISTENT/42")
        assert resp.status_code == 503

    def test_404_when_stop_not_in_stopsahead(self):
        """Stop ID that isn't in stopsAhead for this trip → 404."""
        client = self._get_client(self._build_snapshot())
        resp = client.get(f"/eta/{TRIP_ID}/9999")
        assert resp.status_code == 404

    def test_physics_model_param(self):
        """?model=physics must return model_used='physics'."""
        client = self._get_client(self._build_snapshot())
        resp = client.get(f"/eta/{TRIP_ID}/{NEXT_STOP_ID}?model=physics")
        assert resp.status_code == 200
        assert resp.json()["model_used"] == "physics"

    def test_xgboost_model_param(self):
        """?model=xgboost must return model_used='xgboost' when artifact available."""
        # Train a tiny model and inject the artifact path
        from models.training.generate_data import generate, FEATURES, TARGET
        import numpy as np
        from xgboost import XGBRegressor
        import joblib, tempfile, os

        samples = generate(n_samples=500, seed=42)
        X = np.array([[s[f] for f in FEATURES] for s in samples], dtype=np.float32)
        y = np.array([s[TARGET] for s in samples], dtype=np.float32)
        model = XGBRegressor(n_estimators=30, random_state=42)
        model.fit(X, y)

        with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as f:
            tmp_path = f.name
        try:
            joblib.dump({"model": model, "features": FEATURES}, tmp_path)

            import models.ml_eta_xgb as xgb_mod
            xgb_mod._load_model.cache_clear()

            with mock.patch.object(xgb_mod, "_ARTIFACT_PATH", tmp_path):
                xgb_mod._load_model.cache_clear()
                client = self._get_client(self._build_snapshot())
                resp = client.get(f"/eta/{TRIP_ID}/{NEXT_STOP_ID}?model=xgboost")

            assert resp.status_code == 200
            assert resp.json()["model_used"] == "xgboost"
        finally:
            os.unlink(tmp_path)
            xgb_mod._load_model.cache_clear()

    def test_eta_seconds_physics_formula(self):
        """Physics ETA must match distance / max(speed, 1.4) within 1%."""
        distance, speed = 500.0, 8.33
        client = self._get_client(self._build_snapshot(distance=distance, speed=speed))
        resp = client.get(f"/eta/{TRIP_ID}/{NEXT_STOP_ID}?model=physics")
        assert resp.status_code == 200
        expected = distance / max(speed, 1.4)
        assert resp.json()["eta_seconds"] == pytest.approx(expected, rel=0.01)

    def test_slow_bus_speed_clamped_in_response(self):
        """Bus crawling at 0.5 m/s must have clamped=True in the HTTP response."""
        client = self._get_client(self._build_snapshot(speed=0.5))
        resp = client.get(f"/eta/{TRIP_ID}/{NEXT_STOP_ID}?model=physics")
        assert resp.status_code == 200
        assert resp.json()["clamped"] is True

    def test_zero_distance_returns_zero_eta(self):
        """Bus at the stop (distanceToNextStop=0) must return eta_seconds=0."""
        client = self._get_client(self._build_snapshot(distance=0.0))
        resp = client.get(f"/eta/{TRIP_ID}/{NEXT_STOP_ID}?model=physics")
        assert resp.status_code == 200
        assert resp.json()["eta_seconds"] == pytest.approx(0.0)


# ===========================================================================
# 5. End-to-end: message in → HTTP endpoint out
# ===========================================================================

class TestEndToEnd:
    """
    Simulate the full flow: consumer processes a message, writes Redis snapshot,
    then the HTTP endpoint reads that snapshot and returns a valid ETA.

    This is the closest to a real smoke test without live infrastructure.
    """

    @pytest.mark.asyncio
    async def test_full_pipeline_physics(self):
        """
        1. consumer.handle_message() is called with GPS_CLEANED_MESSAGE.
        2. Capture the Redis setex call to get the written snapshot.
        3. Feed that snapshot to the HTTP endpoint.
        4. Assert response is 200 with valid eta_seconds.
        """
        from consumer import handle_message  # noqa: PLC0415
        from fastapi.testclient import TestClient
        from main import app  # noqa: PLC0415

        redis_write = _make_redis_mock()
        await handle_message(GPS_CLEANED_MESSAGE, redis_write)

        # Extract the snapshot that was written to Redis
        written_snapshot = None
        for call in redis_write.setex.call_args_list:
            if TRIP_ID in call.args[0]:
                written_snapshot = call.args[2]
                break
        assert written_snapshot is not None, "Consumer did not write a snapshot"

        # Feed it to the HTTP endpoint
        redis_read = mock.AsyncMock()
        redis_read.get = mock.AsyncMock(return_value=written_snapshot)

        with mock.patch("routers.eta.get_redis", return_value=redis_read):
            client = TestClient(app)
            resp = client.get(f"/eta/{TRIP_ID}/{NEXT_STOP_ID}?model=physics")

        assert resp.status_code == 200
        body = resp.json()
        assert body["tripId"] == TRIP_ID
        assert body["stopId"] == NEXT_STOP_ID
        assert body["eta_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_full_pipeline_xgboost_fallback_to_physics(self):
        """When XGBoost artifact is missing the pipeline must still return 200."""
        from consumer import handle_message  # noqa: PLC0415
        from fastapi.testclient import TestClient
        from main import app  # noqa: PLC0415

        redis_write = _make_redis_mock()
        with mock.patch("models.ml_eta_xgb._load_model", side_effect=FileNotFoundError):
            await handle_message(GPS_CLEANED_MESSAGE, redis_write)

        written_snapshot = None
        for call in redis_write.setex.call_args_list:
            if TRIP_ID in call.args[0]:
                written_snapshot = call.args[2]
                break
        assert written_snapshot is not None

        redis_read = mock.AsyncMock()
        redis_read.get = mock.AsyncMock(return_value=written_snapshot)

        with mock.patch("routers.eta.get_redis", return_value=redis_read):
            client = TestClient(app)
            resp = client.get(f"/eta/{TRIP_ID}/{NEXT_STOP_ID}?model=xgboost")

        assert resp.status_code == 200
        assert resp.json()["model_used"] in ("physics", "xgboost")

    @pytest.mark.asyncio
    async def test_eta_live_and_http_agree(self):
        """
        eta_seconds in the HTTP response and in the eta:live publish must agree
        within 1 second (both derived from the same snapshot).
        """
        from consumer import handle_message  # noqa: PLC0415
        from fastapi.testclient import TestClient
        from main import app  # noqa: PLC0415

        redis_write = _make_redis_mock()
        await handle_message(GPS_CLEANED_MESSAGE, redis_write)

        # Get eta_seconds from eta:live
        live_eta = None
        for call in redis_write.publish.call_args_list:
            if call.args[0] == "eta:live":
                live_eta = json.loads(call.args[1])["eta_seconds"]
                break
        assert live_eta is not None

        # Get eta_seconds from HTTP endpoint using same snapshot
        written_snapshot = None
        for call in redis_write.setex.call_args_list:
            if TRIP_ID in call.args[0]:
                written_snapshot = call.args[2]
                break

        redis_read = mock.AsyncMock()
        redis_read.get = mock.AsyncMock(return_value=written_snapshot)

        with mock.patch("routers.eta.get_redis", return_value=redis_read):
            client = TestClient(app)
            resp = client.get(f"/eta/{TRIP_ID}/{NEXT_STOP_ID}?model=physics")

        http_eta = resp.json()["eta_seconds"]
        assert abs(http_eta - live_eta) < 1.0, (
            f"eta:live ({live_eta:.2f}s) and HTTP ({http_eta:.2f}s) differ by more than 1s"
        )
