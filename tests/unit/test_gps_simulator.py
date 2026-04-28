# tests/unit/test_gps_simulator.py

import json
import scripts.gps_simulator as gps_simulator
from scripts.gps_simulator import create_message, haversine_km, calculate_bearing


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


def test_calculate_bearing():
    bearing = calculate_bearing(
        79.8612, 6.9271,
        79.8612, 6.9371  # Moving straight North
    )
    assert bearing == 0.0

    bearing_east = calculate_bearing(
        79.8612, 6.9271,
        79.8712, 6.9271  # Moving straight East
    )
    assert bearing_east == 90.0


def test_create_message_has_required_fields():
    payload = create_message(
        79.8612, 6.9271,
        79.8712, 6.9371,
        4
    )

    expected_keys = {
        "busId",
        "tripId",
        "lat",
        "lon",
        "speed",
        "heading",
        "timestamp",
    }

    assert expected_keys == set(payload.keys())


def test_create_message_coordinates_precision():
    payload = create_message(
        79.86123456, 6.92712345,
        79.87129876, 6.93718765,
        4
    )

    assert payload["lat"] == round(payload["lat"], 6)
    assert payload["lon"] == round(payload["lon"], 6)


def test_create_message_speed_non_negative():
    payload = create_message(
        79.8612, 6.9271,
        79.8712, 6.9371,
        4
    )

    assert payload["speed"] >= 0


def test_create_message_timestamp_format():
    payload = create_message(
        79.8612, 6.9271,
        79.8712, 6.9371,
        4
    )

    assert "T" in payload["timestamp"]
    assert payload["timestamp"].endswith("Z")


def test_publish_loop_sends_telemetry_to_configured_topic(monkeypatch):
    sent_messages = []
    loop_stopped = False
    disconnected = False

    class FakeMQTTClient:
        def publish(self, topic, payload):
            sent_messages.append((topic, payload))
            class FakeResult:
                def wait_for_publish(self):
                    pass
            return FakeResult()

        def loop_stop(self):
            nonlocal loop_stopped
            loop_stopped = True

        def disconnect(self):
            nonlocal disconnected
            disconnected = True

    def fake_sleep(_seconds):
        gps_simulator.running = False

    monkeypatch.setattr(gps_simulator, "running", True)
    monkeypatch.setattr(gps_simulator, "get_mqtt_client", lambda: FakeMQTTClient())
    monkeypatch.setattr(
        gps_simulator,
        "load_route_points",
        lambda: [
            (79.8612, 6.9271),
            (79.8712, 6.9371),
        ],
    )
    monkeypatch.setattr(gps_simulator.random, "randint", lambda _min, _max: 4)
    monkeypatch.setattr(gps_simulator.time, "sleep", fake_sleep)

    gps_simulator.publish_loop()

    assert len(sent_messages) == 1
    topic, payload_str = sent_messages[0]
    expected_topic = f"transport/bus/{gps_simulator.settings.bus_id}/location"
    assert topic == expected_topic
    
    payload = json.loads(payload_str)
    assert payload["tripId"] == gps_simulator.settings.trip_id
    assert payload["busId"] == gps_simulator.settings.bus_id
    assert loop_stopped is True
    assert disconnected is True
