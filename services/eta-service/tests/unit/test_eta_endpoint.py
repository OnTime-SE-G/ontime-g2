import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

import main as main_module
from routers import eta as eta_router


class FakeRedis:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value

    def publish(self, channel, value):
        pass


@pytest.fixture(autouse=True)
def patch_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(eta_router, "_get_redis_client", lambda: fake)
    return fake


def test_get_eta_success(patch_redis):
    client = TestClient(main_module.app)
    snapshot = {
        "busId": "BUS-001",
        "routeId": "1",
        "speed": 1.95,
        "nextStopId": 42,
        "distanceToNextStop": 234.5,
        "stopsRemaining": 3,
        "stopsAhead": [
            {"stopId": 42, "stopName": "Kadawatha Junction", "stopOrder": 5, "distanceAlongRouteMeters": 234.5}
        ],
        "routeProgressPct": 65.3,
        "timestamp": "2026-05-05T01:00:00Z",
        "etaSeconds": 120.5,
        "speedClamped": False,
    }

    key = "eta:trip:TRIP-2026-001:snapshot"
    patch_redis.setex(key, 300, json.dumps(snapshot))

    resp = client.get("/api/v1/eta/TRIP-2026-001/42")
    assert resp.status_code == 200
    body = resp.json()
    assert body["tripId"] == "TRIP-2026-001"
    assert body["stopId"] == 42
    assert body["eta_seconds"] > 0
    assert body["model_used"] in {"physics", "xgboost"}


def test_get_eta_missing_snapshot(patch_redis):
    client = TestClient(main_module.app)
    resp = client.get("/api/v1/eta/NO-SUCH-TRIP/1")
    assert resp.status_code == 503


def test_get_eta_stop_not_found(patch_redis):
    client = TestClient(main_module.app)
    snapshot = {
        "busId": "BUS-001",
        "stopsAhead": [{"stopId": 99, "stopName": "Other"}],
        "etaSeconds": 10.0,
    }
    patch_redis.setex("eta:trip:TRIP-2026-002:snapshot", 300, json.dumps(snapshot))

    resp = client.get("/api/v1/eta/TRIP-2026-002/42")
    assert resp.status_code == 404


def test_get_eta_supports_xgboost_model(patch_redis, monkeypatch):
    client = TestClient(main_module.app)
    snapshot = {
        "busId": "BUS-001",
        "routeId": "1",
        "speed": 1.95,
        "stopsRemaining": 3,
        "stopsAhead": [
            {"stopId": 42, "stopName": "Kadawatha Junction", "distanceAlongRouteMeters": 234.5}
        ],
        "timestamp": "2026-05-05T01:00:00Z",
    }
    patch_redis.setex("eta:trip:TRIP-2026-001:snapshot", 300, json.dumps(snapshot))

    from models.inference_router import InferenceOutcome

    fake_result = SimpleNamespace(eta_seconds=88.0, speed_ms=1.95, clamped=False)
    monkeypatch.setattr(
        "routers.eta.route_predict",
        lambda *args, **kwargs: InferenceOutcome(
            result=fake_result, model_used="xgboost", segment_mode="urban"
        ),
    )

    resp = client.get("/api/v1/eta/TRIP-2026-001/42?model=xgboost")
    assert resp.status_code == 200
    assert resp.json()["model_used"] == "xgboost"


def test_get_eta_uses_distance_from_stop_when_present(patch_redis):
    client = TestClient(main_module.app)
    snapshot = {
        "busId": "BUS-001",
        "routeId": "1",
        "speed": 2.0,
        "stopsAhead": [
            {"stopId": 42, "stopName": "Kadawatha Junction", "distanceAlongRouteMeters": 345.0}
        ],
        "etaSeconds": 120.0,
        "speedClamped": False,
        "timestamp": "2026-05-05T01:00:00Z",
    }
    patch_redis.setex("eta:trip:TRIP-2026-003:snapshot", 300, json.dumps(snapshot))

    resp = client.get("/api/v1/eta/TRIP-2026-003/42")

    assert resp.status_code == 200
    assert resp.json()["distance_m"] == pytest.approx(345.0)


def test_get_eta_parses_bytes_snapshot(patch_redis, monkeypatch):
    client = TestClient(main_module.app)
    snapshot = {
        "busId": "BUS-002",
        "stopsAhead": [{"stopId": 7, "stopName": "Stop 7", "distanceAlongRouteMeters": 88.0}],
        "etaSeconds": 33.0,
        "speed": 0.0,
        "speedClamped": True,
        "timestamp": "2026-05-05T01:00:00Z",
    }
    patch_redis.store["eta:trip:TRIP-BYTES:snapshot"] = json.dumps(snapshot).encode("utf-8")

    from models.inference_router import InferenceOutcome

    monkeypatch.setattr(
        "routers.eta.route_predict",
        lambda *args, **kwargs: InferenceOutcome(
            result=SimpleNamespace(eta_seconds=33.0, speed_ms=1.4, clamped=True),
            model_used="physics",
            segment_mode="urban",
        ),
    )

    resp = client.get("/api/v1/eta/TRIP-BYTES/7")

    assert resp.status_code == 200
    assert resp.json()["clamped"] is True


def test_get_eta_rejects_invalid_model(patch_redis):
    client = TestClient(main_module.app)

    resp = client.get("/api/v1/eta/TRIP-2026-001/42?model=badmodel")

    assert resp.status_code == 400


def test_get_eta_uses_xgboost_model_when_requested(patch_redis, monkeypatch):
    client = TestClient(main_module.app)
    snapshot = {
        "busId": "BUS-001",
        "speed": 2.0,
        "stopsRemaining": 2,
        "stopsAhead": [
            {"stopId": 42, "stopName": "Kadawatha Junction", "distanceAlongRouteMeters": 345.0}
        ],
        "timestamp": "2026-05-05T01:00:00Z",
    }
    patch_redis.setex("eta:trip:TRIP-XGB:snapshot", 300, json.dumps(snapshot))

    from models.inference_router import InferenceOutcome

    fake_eta = SimpleNamespace(eta_seconds=77.0, speed_ms=2.0, clamped=False)
    monkeypatch.setattr(
        "routers.eta.route_predict",
        lambda *args, **kwargs: InferenceOutcome(
            result=fake_eta, model_used="xgboost", segment_mode="urban"
        ),
    )

    resp = client.get("/api/v1/eta/TRIP-XGB/42?model=xgboost")

    assert resp.status_code == 200
    body = resp.json()
    assert body["eta_seconds"] == pytest.approx(77.0)
    assert body["model_used"] == "xgboost"
