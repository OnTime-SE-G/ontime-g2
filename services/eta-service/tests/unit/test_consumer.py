import json
import threading
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from consumer import ETA_LIVE_CHANNEL, EtaFeatureConsumer


class FakeRedis:
    def __init__(self):
        self.calls = []

    def setex(self, key, ttl, value):
        self.calls.append(("setex", key, ttl, value))

    def publish(self, channel, value):
        self.calls.append(("publish", channel, value))


def make_payload(**overrides):
    payload = {
        "tripId": "TRIP-2026-001",
        "busId": "BUS-001",
        "routeId": "ROUTE-1",
        "nextStopId": 42,
        "distanceToNextStop": 234.5,
        "stopsRemaining": 3,
        "stopsAhead": [
            {
                "stopId": 42,
                "stopName": "Kadawatha Junction",
                "stopOrder": 5,
                "distanceAlongRouteMeters": 234.5,
            },
            {
                "stopId": 43,
                "stopName": "Gampaha",
                "stopOrder": 6,
                "distanceAlongRouteMeters": 1820.0,
            },
        ],
        "speed": 1.95,
        "routeProgressPct": 65.3,
        "timestamp": "2026-05-05T01:00:00Z",
    }
    payload.update(overrides)
    return payload


def test_process_payload_writes_snapshot_and_live_event():
    redis_client = FakeRedis()
    consumer = EtaFeatureConsumer(redis_client, default_model="physics")

    result = consumer.process_payload(make_payload())

    assert result["snapshot_key"] == "eta:trip:TRIP-2026-001:snapshot"
    assert result["eta_result"].eta_seconds == pytest.approx(234.5 / 1.95)
    assert redis_client.calls[0][0] == "setex"
    assert redis_client.calls[0][1] == "eta:trip:TRIP-2026-001:snapshot"
    assert redis_client.calls[0][2] == 300

    snapshot = json.loads(redis_client.calls[0][3])
    assert snapshot["nextStopId"] == 42
    assert snapshot["distanceToNextStop"] == pytest.approx(234.5)
    assert snapshot["stopsRemaining"] == 3
    assert snapshot["stopsAhead"][0]["stopId"] == 42
    assert snapshot["stopsAhead"][1]["stopOrder"] == 6
    assert len(snapshot["stopEtas"]) == 2
    assert snapshot["stopEtas"][0]["stopId"] == 42
    assert snapshot["stopEtas"][1]["stopId"] == 43

    assert redis_client.calls[1][0] == "publish"
    assert redis_client.calls[1][1] == ETA_LIVE_CHANNEL
    live_event = json.loads(redis_client.calls[1][2])
    assert live_event["event"] == "eta_update"
    assert live_event["tripId"] == "TRIP-2026-001"
    assert live_event["stopId"] == 42
    assert live_event["stopName"] == "Kadawatha Junction"
    assert live_event["model_used"] == "physics"
    assert len(live_event["stop_etas"]) == 2
    assert live_event["stop_etas"][0]["stop_id"] == 42
    assert live_event["stop_etas"][1]["stop_id"] == 43
    assert result["snapshot"]["modelUsed"] == "physics"


def test_process_payload_clamps_zero_speed_for_eta():
    redis_client = FakeRedis()
    consumer = EtaFeatureConsumer(redis_client, default_model="physics")

    result = consumer.process_payload(make_payload(speed=0.0, distanceToNextStop=140.0))

    assert result["eta_result"].clamped is True
    assert result["eta_result"].speed_ms == pytest.approx(1.4)
    assert result["eta_result"].eta_seconds == pytest.approx(100.0)


def test_process_payload_skips_off_route_field():
    redis_client = FakeRedis()
    consumer = EtaFeatureConsumer(redis_client, default_model="physics")

    result = consumer.process_payload(make_payload(offRoute=True, offRouteDistanceM=83.4))

    assert result == {"skipped": True, "reason": "off_route"}
    assert redis_client.calls == []


def test_process_payload_skips_snake_case_on_route_false():
    redis_client = FakeRedis()
    consumer = EtaFeatureConsumer(redis_client, default_model="physics")

    result = consumer.process_payload(make_payload(on_route=False, routeDeviationMeters=83.4))

    assert result == {"skipped": True, "reason": "off_route"}
    assert redis_client.calls == []


def test_process_payload_skips_inactive_trip_status():
    redis_client = FakeRedis()
    consumer = EtaFeatureConsumer(redis_client, default_model="physics")

    result = consumer.process_payload(make_payload(trip_status="INACTIVE"))

    assert result == {"skipped": True, "reason": "inactive_trip"}
    assert redis_client.calls == []


def test_process_message_decodes_json_bytes():
    redis_client = FakeRedis()
    consumer = EtaFeatureConsumer(redis_client, default_model="physics")
    message = type("KafkaMessage", (), {"value": json.dumps(make_payload()).encode("utf-8")})()

    result = consumer.process_message(message)

    assert result["live_event"]["tripId"] == "TRIP-2026-001"
    assert redis_client.calls[0][0] == "setex"


def test_missing_required_fields_raise_clear_error():
    redis_client = FakeRedis()
    consumer = EtaFeatureConsumer(redis_client, default_model="physics")

    with pytest.raises(ValueError, match="Missing ETA feature fields"):
        consumer.process_payload({"tripId": "TRIP-2026-001"})


def test_decode_message_accepts_mapping_directly():
    consumer = EtaFeatureConsumer(FakeRedis(), default_model="physics")
    payload = make_payload()

    decoded = consumer.decode_message(payload)

    assert decoded["tripId"] == payload["tripId"]


def test_snapshot_key_uses_trip_id():
    consumer = EtaFeatureConsumer(FakeRedis(), default_model="physics")

    assert consumer.snapshot_key("TRIP-123") == "eta:trip:TRIP-123:snapshot"


def test_create_kafka_consumer_uses_injected_factory():
    fake_client = FakeRedis()
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)
        return "fake-consumer"

    consumer = EtaFeatureConsumer(fake_client, default_model="physics", consumer_factory=factory)

    assert consumer.create_kafka_consumer() == "fake-consumer"
    assert calls[0]["bootstrap_servers"] == "broker:29092"
    assert calls[0]["group_id"] == "eta-service"
    assert calls[0]["topic_name"] == "transport-eta-features"


def test_process_payload_supports_custom_snapshot_ttl():
    redis_client = FakeRedis()
    consumer = EtaFeatureConsumer(redis_client, default_model="physics", snapshot_ttl_seconds=42)

    consumer.process_payload(make_payload())

    assert redis_client.calls[0][2] == 42


def test_process_payload_uses_xgboost_when_available(monkeypatch):
    redis_client = FakeRedis()
    consumer = EtaFeatureConsumer(redis_client, default_model="xgboost")

    fake_result = SimpleNamespace(eta_seconds=77.0, speed_ms=1.95, clamped=False)
    monkeypatch.setattr(
        "consumer.EtaFeatureConsumer._predict_eta",
        lambda self, distance_m, speed_ms, stops_remaining, timestamp, model_name=None, **kwargs: (fake_result, "xgboost"),
    )

    result = consumer.process_payload(make_payload())

    assert result["model_used"] == "xgboost"
    assert result["eta_result"].eta_seconds == pytest.approx(77.0)
    assert result["snapshot"]["modelUsed"] == "xgboost"


def test_process_payload_falls_back_to_physics_when_xgboost_fails(monkeypatch):
    redis_client = FakeRedis()
    consumer = EtaFeatureConsumer(redis_client, default_model="xgboost")

    monkeypatch.setattr(
        "consumer.EtaFeatureConsumer._predict_eta",
        lambda self, distance_m, speed_ms, stops_remaining, timestamp, model_name=None, **kwargs: (SimpleNamespace(eta_seconds=0.0, speed_ms=speed_ms, clamped=False), "physics"),
    )

    result = consumer.process_payload(make_payload())

    assert result["model_used"] == "physics"
    assert result["live_event"]["model_used"] == "physics"


def test_process_payload_uses_sarima_when_available(monkeypatch):
    redis_client = FakeRedis()
    consumer = EtaFeatureConsumer(redis_client, default_model="sarima")

    fake_module = SimpleNamespace(
        forecast_eta_sarima=lambda route_id, stop_id, dt=None: 66.0
    )
    monkeypatch.setitem(sys.modules, "models.sarima_eta", fake_module)

    result = consumer.process_payload(make_payload())

    assert result["model_used"] == "sarima"
    assert result["eta_result"].eta_seconds == pytest.approx(66.0)
    assert result["snapshot"]["modelUsed"] == "sarima"
    assert result["live_event"]["model_used"] == "sarima"
    assert result["live_event"]["stop_etas"][0]["model_used"] == "sarima"


def test_process_payload_labels_physics_when_xgboost_artifact_missing(monkeypatch):
    redis_client = FakeRedis()
    consumer = EtaFeatureConsumer(redis_client, default_model="xgboost")

    fake_module = SimpleNamespace(
        predict_eta_xgb_with_fallback=lambda *args, **kwargs: (
            SimpleNamespace(eta_seconds=120.0, speed_ms=1.95, clamped=False),
            "physics",
        )
    )
    monkeypatch.setitem(sys.modules, "models.ml_eta_xgb", fake_module)

    result = consumer.process_payload(make_payload())

    assert result["model_used"] == "physics"
    assert result["snapshot"]["modelUsed"] == "physics"
    assert result["live_event"]["model_used"] == "physics"


def test_consume_forever_processes_kafka_messages_and_closes_consumer():
    redis_client = FakeRedis()
    processed_messages = []

    class FakeKafkaConsumer:
        def __iter__(self):
            yield type("KafkaMessage", (), {"value": json.dumps(make_payload()).encode("utf-8")})()

        def close(self):
            processed_messages.append("closed")

    consumer = EtaFeatureConsumer(
        redis_client,
        consumer_factory=lambda **kwargs: FakeKafkaConsumer(),
    )

    consumer.consume_forever(stop_event=threading.Event())

    assert redis_client.calls[0][0] == "setex"
    assert processed_messages == ["closed"]
