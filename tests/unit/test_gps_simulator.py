# tests/unit/test_gps_simulator.py

from types import SimpleNamespace
from typing import Any, cast

import pytest

import scripts.gps_simulator as gps_simulator
from scripts.gps_simulator import (
    choose_next_bus,
    create_location_message,
    create_status_message,
    haversine_km,
    publish_json,
)


def test_haversine_zero_distance():
    distance = haversine_km(
        79.8612, 6.9271,
        79.8612, 6.9271
    )

    assert distance == 0


def test_haversine_positive_distance():
    distance = haversine_km(
        79.8612, 6.9271,
        79.8712, 6.9371
    )

    assert distance > 0


def test_create_status_message_has_required_fields(monkeypatch):
    monkeypatch.setattr(
        gps_simulator,
        "now_utc",
        lambda: "2026-04-27T12:00:00Z"
    )

    payload = create_status_message(
        bus_id=10,
        route_id=20,
        status="STARTED"
    )

    assert payload == {
        "type": "STATUS",
        "status": "STARTED",
        "busId": 10,
        "routeId": 20,
        "timestamp": "2026-04-27T12:00:00Z",
    }


def test_create_location_message_has_required_fields(monkeypatch):
    monkeypatch.setattr(
        gps_simulator,
        "now_utc",
        lambda: "2026-04-27T12:00:00Z"
    )
    monkeypatch.setattr(
        gps_simulator.random,
        "choice",
        lambda values: values[0]
    )
    monkeypatch.setattr(
        gps_simulator.random,
        "randint",
        lambda _min, _max: 40
    )

    payload = create_location_message(
        bus_id=10,
        route_id=20,
        prev_lon=79.8612,
        prev_lat=6.9271,
        lon=79.8712,
        lat=6.9371
    )

    expected_keys = {
        "type",
        "busId",
        "routeId",
        "lat",
        "lng",
        "speed",
        "crowdStatus",
        "timestamp",
    }

    assert set(payload.keys()) == expected_keys
    assert payload["type"] == "LOCATION"
    assert payload["busId"] == 10
    assert payload["routeId"] == 20
    assert payload["speed"] == 40
    assert payload["crowdStatus"] == "NOT_FULL"
    assert payload["timestamp"] == "2026-04-27T12:00:00Z"


def test_create_location_message_coordinates_precision():
    payload = create_location_message(
        bus_id=10,
        route_id=20,
        prev_lon=79.86123456,
        prev_lat=6.92712345,
        lon=79.87129876,
        lat=6.93718765
    )

    assert payload["lat"] == round(payload["lat"], 6)
    assert payload["lng"] == round(payload["lng"], 6)


def test_create_location_message_speed_between_30_and_50():
    payload = create_location_message(
        bus_id=10,
        route_id=20,
        prev_lon=79.8612,
        prev_lat=6.9271,
        lon=79.8712,
        lat=6.9371
    )

    assert 30 <= payload["speed"] <= 50


def test_create_location_message_uses_random_speed(monkeypatch):
    monkeypatch.setattr(
        gps_simulator.random,
        "randint",
        lambda _min, _max: 45
    )

    payload = create_location_message(
        bus_id=10,
        route_id=20,
        prev_lon=79.8612,
        prev_lat=6.9271,
        lon=79.8712,
        lat=6.9371
    )

    assert payload["speed"] == 45


def test_create_location_message_valid_crowd_status():
    payload = create_location_message(
        bus_id=10,
        route_id=20,
        prev_lon=79.8612,
        prev_lat=6.9271,
        lon=79.8712,
        lat=6.9371
    )

    assert payload["crowdStatus"] in {
        "NOT_FULL",
        "SEMI_FULL",
        "FULL",
    }


def test_create_location_message_timestamp_format():
    payload = create_location_message(
        bus_id=10,
        route_id=20,
        prev_lon=79.8612,
        prev_lat=6.9271,
        lon=79.8712,
        lat=6.9371
    )

    assert "T" in payload["timestamp"]
    assert payload["timestamp"].endswith("Z")


def test_publish_json_publishes_serialized_payload_with_qos_one():
    published_messages = []

    class FakeClient:
        def publish(self, topic, payload, qos):
            published_messages.append((topic, payload, qos))

    publish_json(
        cast(Any, FakeClient()),
        "transport/bus/10/location",
        {"type": "STATUS", "busId": 10}
    )

    topic, payload_json, qos = published_messages[0]
    payload = gps_simulator.json.loads(payload_json)

    assert topic == "transport/bus/10/location"
    assert payload == {"type": "STATUS", "busId": 10}
    assert qos == 1


def test_choose_next_bus_returns_none_when_route_has_no_buses():
    assert choose_next_bus(1, {}) is None


def test_choose_next_bus_excludes_active_bus_when_possible(monkeypatch):
    buses = [
        SimpleNamespace(id=1),
        SimpleNamespace(id=2),
    ]

    monkeypatch.setattr(
        gps_simulator.random,
        "choice",
        lambda values: values[0]
    )

    selected = choose_next_bus(
        route_id=10,
        buses_by_route=cast(Any, {10: buses}),
        active_bus_id=1
    )
    assert selected is not None
    assert selected.id == 2


def test_choose_next_bus_reuses_active_bus_when_only_candidate(monkeypatch):
    bus = SimpleNamespace(id=1)

    monkeypatch.setattr(
        gps_simulator.random,
        "choice",
        lambda values: values[0]
    )

    selected = choose_next_bus(
        route_id=10,
        buses_by_route=cast(Any, {10: [bus]}),
        active_bus_id=1
    )

    assert selected is bus


def test_publish_loop_publishes_status_and_location_messages(monkeypatch):
    published_messages = []
    loop_stopped = False
    disconnected = False

    route = SimpleNamespace(id=20)
    bus = SimpleNamespace(id=10, route_id=20)

    class FakeClient:
        def publish(self, topic, payload, qos):
            published_messages.append((topic, payload, qos))

        def loop_stop(self):
            nonlocal loop_stopped
            loop_stopped = True

        def disconnect(self):
            nonlocal disconnected
            disconnected = True

    def fake_sleep(_seconds):
        gps_simulator.running = False

    monkeypatch.setattr(gps_simulator, "running", True)
    monkeypatch.setattr(gps_simulator, "get_mqtt_client", lambda: FakeClient())
    monkeypatch.setattr(
        gps_simulator,
        "load_routes_and_buses",
        lambda: (
            [route],
            {20: [bus]},
            {
                20: [
                    (79.8612, 6.9271),
                    (79.8712, 6.9371),
                ]
            }
        )
    )
    monkeypatch.setattr(
        gps_simulator.random,
        "choice",
        lambda values: values[0]
    )
    monkeypatch.setattr(
        gps_simulator.random,
        "randint",
        lambda _min, _max: 4
    )
    monkeypatch.setattr(gps_simulator.time, "sleep", fake_sleep)

    gps_simulator.publish_loop()

    assert len(published_messages) == 2

    start_topic, start_json, start_qos = published_messages[0]
    location_topic, location_json, location_qos = published_messages[1]
    start_payload = gps_simulator.json.loads(start_json)
    location_payload = gps_simulator.json.loads(location_json)

    assert start_topic == "transport/bus/10/location"
    assert start_qos == 1
    assert start_payload["type"] == "STATUS"
    assert start_payload["status"] == "STARTED"
    assert start_payload["busId"] == 10
    assert start_payload["routeId"] == 20

    assert location_topic == "transport/bus/10/location"
    assert location_qos == 1
    assert location_payload["type"] == "LOCATION"
    assert location_payload["busId"] == 10
    assert location_payload["routeId"] == 20
    assert loop_stopped is True
    assert disconnected is True


def test_publish_loop_stops_route_and_starts_next_bus(monkeypatch):
    published_messages = []

    route = SimpleNamespace(id=20)
    first_bus = SimpleNamespace(id=10, route_id=20)
    next_bus = SimpleNamespace(id=11, route_id=20)

    class FakeClient:
        def publish(self, topic, payload, qos):
            published_messages.append((topic, payload, qos))

        def loop_stop(self):
            pass

        def disconnect(self):
            pass

    def fake_sleep(_seconds):
        gps_simulator.running = False

    monkeypatch.setattr(gps_simulator, "running", True)
    monkeypatch.setattr(gps_simulator, "get_mqtt_client", lambda: FakeClient())
    monkeypatch.setattr(
        gps_simulator,
        "load_routes_and_buses",
        lambda: (
            [route],
            {20: [first_bus, next_bus]},
            {20: [(79.8612, 6.9271)]}
        )
    )
    monkeypatch.setattr(
        gps_simulator.random,
        "choice",
        lambda values: values[0]
    )
    monkeypatch.setattr(gps_simulator.time, "sleep", fake_sleep)

    gps_simulator.publish_loop()

    payloads = [
        gps_simulator.json.loads(payload_json)
        for _topic, payload_json, _qos in published_messages
    ]

    assert payloads == [
        {
            "type": "STATUS",
            "status": "STARTED",
            "busId": 10,
            "routeId": 20,
            "timestamp": payloads[0]["timestamp"],
        },
        {
            "type": "STATUS",
            "status": "STOPPED",
            "busId": 10,
            "routeId": 20,
            "timestamp": payloads[1]["timestamp"],
        },
        {
            "type": "STATUS",
            "status": "STARTED",
            "busId": 11,
            "routeId": 20,
            "timestamp": payloads[2]["timestamp"],
        },
    ]


def test_publish_loop_requires_at_least_one_route(monkeypatch):
    class FakeClient:
        def loop_stop(self):
            pass

        def disconnect(self):
            pass

    monkeypatch.setattr(gps_simulator, "get_mqtt_client", lambda: FakeClient())
    monkeypatch.setattr(
        gps_simulator,
        "load_routes_and_buses",
        lambda: (_ for _ in ()).throw(
            ValueError("No routes found. Run seed_routes.py first.")
        )
    )

    with pytest.raises(ValueError, match="No routes found"):
        gps_simulator.publish_loop()
