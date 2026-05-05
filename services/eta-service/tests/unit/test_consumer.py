import json
import threading

import pytest

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
    consumer = EtaFeatureConsumer(redis_client)

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

    assert redis_client.calls[1][0] == "publish"
    assert redis_client.calls[1][1] == ETA_LIVE_CHANNEL
    live_event = json.loads(redis_client.calls[1][2])
    assert live_event["event"] == "eta_update"
    assert live_event["tripId"] == "TRIP-2026-001"
    assert live_event["stopId"] == 42
    assert live_event["stopName"] == "Kadawatha Junction"
    assert live_event["model_used"] == "physics"


def test_process_payload_clamps_zero_speed_for_eta():
    redis_client = FakeRedis()
    consumer = EtaFeatureConsumer(redis_client)

    result = consumer.process_payload(make_payload(speed=0.0, distanceToNextStop=140.0))

    assert result["eta_result"].clamped is True
    assert result["eta_result"].speed_ms == pytest.approx(1.4)
    assert result["eta_result"].eta_seconds == pytest.approx(100.0)


def test_process_message_decodes_json_bytes():
    redis_client = FakeRedis()
    consumer = EtaFeatureConsumer(redis_client)
    message = type("KafkaMessage", (), {"value": json.dumps(make_payload()).encode("utf-8")})()

    result = consumer.process_message(message)

    assert result["live_event"]["tripId"] == "TRIP-2026-001"
    assert redis_client.calls[0][0] == "setex"


def test_missing_required_fields_raise_clear_error():
    redis_client = FakeRedis()
    consumer = EtaFeatureConsumer(redis_client)

    with pytest.raises(ValueError, match="Missing ETA feature fields"):
        consumer.process_payload({"tripId": "TRIP-2026-001"})


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
